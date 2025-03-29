package net.util;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;

public class ApiCaller {
	/**
	 * Fetches a mod from Modrinth by its slug, filtered by a specific game version
	 * and loader, then downloads the most recent matching file (checking versions in reverse).
	 *
	 * @param slug              The Modrinth project slug (e.g., "itemlore" or a full URL to strip).
	 * @param targetGameVersion The game version you want (e.g. "1.21.3").
	 * @param destination       The folder path where the file will be downloaded (e.g., "./downloads").
	 */
	public static void apiGrabMod(String slug, String targetGameVersion, String destination) {
		OkHttpClient client = new OkHttpClient();

		// 1) Strip "https://modrinth.com/mod/" if present
		slug = slug.replaceFirst("^(https?://)?(www\\.)?modrinth\\.com/mod/", "");

		// 2) Fetch the project details
		String projectUrl = "https://api.modrinth.com/v2/project/" + slug;

		Request projectRequest = new Request.Builder().url(projectUrl).header("Accept", "application/json").build();

		try (Response projectResponse = client.newCall(projectRequest).execute()) {
			if (!projectResponse.isSuccessful()) {
				System.out.println("[ERROR] Project request failed. HTTP code: " + projectResponse.code());
				return;
			}

			assert projectResponse.body() != null;
			String projectJson = projectResponse.body().string();

			// Parse the project JSON
			JsonElement projectRoot = JsonParser.parseString(projectJson);

			if (!projectRoot.isJsonObject()) {
				System.out.println("[ERROR] Project JSON is not an object.");
				return;
			}

			JsonObject projectObj = projectRoot.getAsJsonObject();

			// 3) Get the version IDs array
			if (!projectObj.has("versions") || !projectObj.get("versions").isJsonArray()) {
				System.out.println("[ERROR] 'versions' field is missing or not an array.");
				return;
			}

			JsonArray versionIds = projectObj.get("versions").getAsJsonArray();

			if (versionIds.isEmpty()) {
				System.out.println("[ERROR] No version IDs found in the project.");
				return;
			}

			// Ensure the destination directory exists
			File dir = new File(destination);

			if (!dir.exists()) {
				if (dir.mkdirs()) {
				}
			}

			// 4) Iterate version IDs in reverse order
			//    (assuming the last entry in "versions" is the newest)
			boolean foundMatch = false;

			for (int i = versionIds.size() - 1; i >= 0; i--) {
				String versionId = versionIds.get(i).getAsString();

				// 4a) Fetch the version details
				String versionUrl = "https://api.modrinth.com/v2/version/" + versionId;

				Request versionRequest = new Request.Builder().url(versionUrl).header("Accept", "application/json").build();

				try (Response versionResponse = client.newCall(versionRequest).execute()) {
					if (!versionResponse.isSuccessful()) {
						System.out.println("[WARN] Failed to fetch version " + versionId + ". HTTP: " + versionResponse.code());
						continue; // skip to next
					}

					assert versionResponse.body() != null;
					String versionJson = versionResponse.body().string();

					JsonElement versionRoot = JsonParser.parseString(versionJson);

					if (!versionRoot.isJsonObject()) {
						System.out.println("[WARN] Version JSON is not an object for ID " + versionId);
						continue;
					}

					JsonObject versionObj = versionRoot.getAsJsonObject();

					// 4b) Check if "game_versions" contains our targetGameVersion
					if (!versionObj.has("game_versions") || !versionObj.get("game_versions").isJsonArray()) {
						System.out.println("[WARN] 'game_versions' missing or not array for " + versionId);
						continue;
					}

					JsonArray gameVersions = versionObj.get("game_versions").getAsJsonArray();

					boolean matchesVersion = false;

					for (JsonElement gvElement : gameVersions) {
						if (gvElement.getAsString().equalsIgnoreCase(targetGameVersion)) {
							matchesVersion = true;
							break;
						}
					}

					if (!matchesVersion) {
						continue; // check the next version
					}

					// 4c) Check if "loaders" contains our targetLoader
					if (!versionObj.has("loaders") || !versionObj.get("loaders").isJsonArray()) {
						System.out.println("[WARN] 'loaders' missing or not array for " + versionId);
						continue;
					}

					JsonArray loadersArray = versionObj.get("loaders").getAsJsonArray();

					boolean matchesLoader = false;

					for (JsonElement loaderElem : loadersArray) {
						if (loaderElem.getAsString().equalsIgnoreCase("fabric")) {
							matchesLoader = true;
							break;
						}
					}

					if (!matchesLoader) {
						continue; // check the next version
					}

					// If we reach here, we found a version that supports BOTH the targetGameVersion and loader
					System.out.println("[INFO] Found matching version ID: " + versionId);

					// 4d) Now find the primary file or first file
					if (!versionObj.has("files") || !versionObj.get("files").isJsonArray()) {
						System.out.println("[WARN] No 'files' array found for version ID " + versionId);
						continue;
					}

					JsonArray filesArray = versionObj.get("files").getAsJsonArray();

					if (filesArray.isEmpty()) {
						System.out.println("[WARN] Empty files array for version ID " + versionId);
						continue;
					}

					JsonObject primaryFile = null;

					for (JsonElement fileElem : filesArray) {
						JsonObject fileObj = fileElem.getAsJsonObject();

						if (fileObj.has("primary") && fileObj.get("primary").getAsBoolean()) {
							primaryFile = fileObj;
							break;
						}
					}

					if (primaryFile == null) {
						// fallback: use the first file
						primaryFile = filesArray.get(0).getAsJsonObject();
					}

					String downloadUrl = primaryFile.get("url").getAsString();
					String filename = primaryFile.get("filename").getAsString();
					System.out.println("[INFO] Download URL: " + downloadUrl);
					System.out.println("[INFO] Filename: " + filename);

					// 4e) Download the file
					Request fileRequest = new Request.Builder().url(downloadUrl).build();

					try (Response fileResp = client.newCall(fileRequest).execute()) {
						if (!fileResp.isSuccessful()) {
							System.out.println("[ERROR] Failed to download file. HTTP code: " + fileResp.code());
							continue;
						}

						// Write file to disk
						File outFile = new File(dir, filename);
						assert fileResp.body() != null;

						try (InputStream in = fileResp.body().byteStream(); FileOutputStream fos = new FileOutputStream(outFile)) {
							byte[] buffer = new byte[8192];
							int bytesRead;

							while ((bytesRead = in.read(buffer)) != -1) {
								fos.write(buffer, 0, bytesRead);
							}
						}

						System.out.println("[INFO] Successfully downloaded " + filename);
					} catch (IOException e) {
						System.out.println("[ERROR] Exception while downloading file: " + e.getMessage());
						e.printStackTrace();
					}

					// We found and downloaded the matching version, so we can stop
					foundMatch = true;
					break;
				} catch (IOException e) {
					System.out.println("[ERROR] Exception while fetching version " + versionId + ": " + e.getMessage());
					e.printStackTrace();
				}
			}

			if (!foundMatch) {
				System.out.println("[INFO] No version found matching game version '" + targetGameVersion + "' and loader '" + "fabric" + "'.");
			}
		} catch (IOException e) {
			System.out.println("[ERROR] Exception while fetching project: " + e.getMessage());
			e.printStackTrace();
		}
	}

	// Optional main method for quick testing
	public static void test(String[] args) {
		// Example usage: "itemlore" for game version "1.21.3" and "fabric"
		//apiGrabMod("https://modrinth.com/mod/itemlore", "1.21.4", "./downloads");
		//apiGrabMod("modrinth.com/mod/itemlore", "1.21.4", "./downloads");
		//apiGrabMod("https://modrinth.com/mod/xaeros-minimap", "1.21.3",  "./downloads");
		//apiGrabMod("https://modrinth.com/mod/xaeros-world-map", "1.21.3",  "./downloads");
	}
}
