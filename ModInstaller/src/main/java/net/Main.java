package net;
import net.util.ApiCaller;
import net.util.MainGui;

import javax.swing.*;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.io.IOException;
import java.util.List;

public class Main {
    public static void main(String[] args) {
        if (args.length == 0) {
            // No command-line arguments: launch the GUI.
            SwingUtilities.invokeLater(() -> new MainGui().setVisible(true));
        } else {
            // Command-line arguments present: run CLI mode.
            launcher(args);
        }
    }

    public static void launcher(String[] args) {
        if (args.length < 3) {
            System.out.println("Usage: java -jar ModInstaller.jar <modSlugs or file.txt> <gameVersion> <destination>");
            System.out.println("Example with file: java -jar ModInstaller.jar mods.txt 1.21.3 ./downloads");
            System.out.println("Example with comma-separated slugs: java -jar ModInstaller.jar \"itemlore,xaeros-minimap\" 1.21.3 ./downloads");
            return;
        }

        String slugsInput = args[0];
        String gameVersion = args[1];
        String destination = args[2];

        List<String> modSlugs;
        if (slugsInput.toLowerCase().endsWith(".txt")) {
            try {
                // Read each line of the file as a separate mod slug.
                modSlugs = Files.readAllLines(Paths.get(slugsInput));
            } catch (IOException e) {
                System.err.println("Error reading file: " + slugsInput);
                e.printStackTrace();
                return;
            }
        } else {
            // Fallback: treat the argument as a comma-separated list of mod slugs.
            modSlugs = List.of(slugsInput.split(","));
        }

        for (String slug : modSlugs) {
            if (slug.trim().isEmpty()) {
                continue;
            }
            System.out.println("Processing mod: " + slug.trim());
            ApiCaller.apiGrabMod(slug.trim(), gameVersion, destination);
        }
    }
}
