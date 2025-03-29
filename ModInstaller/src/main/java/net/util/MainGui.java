package net.util;
import net.util.ApiCaller;

import javax.swing.*;
import java.awt.*;
import java.awt.event.ActionEvent;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.io.IOException;
import java.util.List;

public class MainGui extends JFrame {
    private JTextField inputField;
    private JTextField versionField;
    private JTextField destinationField;
    private JTextArea outputArea;
    private JButton browseInputButton;
    private JButton browseDestinationButton;
    private JButton startButton;

    public MainGui() {
        setTitle("Mod Installer");
        setSize(500, 400);
        setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        setLocationRelativeTo(null); // Center the window

        // Create a panel for input fields and buttons
        JPanel inputPanel = new JPanel(new GridLayout(4, 3, 5, 5));

        // Mod slugs input field and browse button
        inputPanel.add(new JLabel("Mod Slugs or File (.txt):"));
        inputField = new JTextField();
        inputPanel.add(inputField);
        browseInputButton = new JButton("Browse");
        inputPanel.add(browseInputButton);

        // Game version field
        inputPanel.add(new JLabel("Game Version:"));
        versionField = new JTextField();
        inputPanel.add(versionField);
        inputPanel.add(new JLabel()); // filler

        // Destination directory field and browse button
        inputPanel.add(new JLabel("Destination Directory:"));
        destinationField = new JTextField();
        inputPanel.add(destinationField);
        browseDestinationButton = new JButton("Browse");
        inputPanel.add(browseDestinationButton);

        // Start download button
        startButton = new JButton("Start Download");
        inputPanel.add(startButton);

        // Set layout and add the input panel to the frame
        setLayout(new BorderLayout());
        add(inputPanel, BorderLayout.NORTH);

        // Output area for logging progress
        outputArea = new JTextArea();
        outputArea.setEditable(false);
        JScrollPane scrollPane = new JScrollPane(outputArea);
        add(scrollPane, BorderLayout.CENTER);

        // Action for browsing input file
        browseInputButton.addActionListener((ActionEvent e) -> {
            JFileChooser fileChooser = new JFileChooser();
            int option = fileChooser.showOpenDialog(MainGui.this);
            if (option == JFileChooser.APPROVE_OPTION) {
                File file = fileChooser.getSelectedFile();
                inputField.setText(file.getAbsolutePath());
            }
        });

        // Action for browsing destination folder
        browseDestinationButton.addActionListener((ActionEvent e) -> {
            JFileChooser folderChooser = new JFileChooser();
            folderChooser.setFileSelectionMode(JFileChooser.DIRECTORIES_ONLY);
            int option = folderChooser.showOpenDialog(MainGui.this);
            if (option == JFileChooser.APPROVE_OPTION) {
                File folder = folderChooser.getSelectedFile();
                destinationField.setText(folder.getAbsolutePath());
            }
        });

        // Action for starting the download process
        startButton.addActionListener((ActionEvent e) -> startDownload());
    }

    private void startDownload() {
        String input = inputField.getText().trim();
        String version = versionField.getText().trim();
        String destination = destinationField.getText().trim();

        if (input.isEmpty() || version.isEmpty() || destination.isEmpty()) {
            JOptionPane.showMessageDialog(this, "Please fill in all fields.", "Missing Input", JOptionPane.WARNING_MESSAGE);
            return;
        }

        // Run the download process in a background thread to keep the UI responsive
        new Thread(() -> {
            List<String> modSlugs;
            if (input.toLowerCase().endsWith(".txt")) {
                try {
                    modSlugs = Files.readAllLines(Paths.get(input));
                } catch (IOException ex) {
                    SwingUtilities.invokeLater(() -> outputArea.append("Error reading file: " + input + "\n"));
                    return;
                }
            } else {
                modSlugs = List.of(input.split(","));
            }

            for (String slug : modSlugs) {
                if (slug.trim().isEmpty()) {
                    continue;
                }
                SwingUtilities.invokeLater(() -> outputArea.append("Processing mod: " + slug.trim() + "\n"));
                ApiCaller.apiGrabMod(slug.trim(), version, destination);
                SwingUtilities.invokeLater(() -> outputArea.append("Finished processing: " + slug.trim() + "\n"));
            }

            SwingUtilities.invokeLater(() -> outputArea.append("All mods processed.\n"));
        }).start();
    }

    public static void main(String[] args) {
        SwingUtilities.invokeLater(() -> new MainGui().setVisible(true));
    }
}
