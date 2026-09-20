# Marketplace submission draft

Title: **[Plugin]: Network**

Repository URL: https://github.com/dagnele/omarchy-network

Category: System

Tags: Bar, Quickshell, System

## Maintainer notes

Network is an independent network widget for the Omarchy Quickshell bar, based on the MIT-licensed built-in Network plugin. It adds an eye toggle for password entry and camera-only Wi-Fi QR joining, with a green detection square and explicit Join confirmation. The original Omarchy attribution is retained in LICENSE and UPSTREAM.md.

The plugin has a distinct ID, `dagnele.network`, and does not automatically replace other widgets or modify packaged files. Installation and removal use Omarchy's standard plugin commands. The README documents the explicit optional switch from the original Network widget.

Runtime dependencies are Python, PyGObject/libnm, ZBar, Qt Multimedia with its FFmpeg backend, NetworkManager, and the current Omarchy shell. QR fixtures for development additionally use qrencode. No installer hooks, remote builds, telemetry, or automatic privilege escalation are included. Camera frames are decoded locally in a private temporary directory, and QR passwords stay in the worker process until supplied to NetworkManager through libnm. The preview is a simulated UI state and contains no real camera footage or credentials.

Developed against Omarchy 4.0.4-1, Quickshell 0.3.1, Qt Multimedia 6.11.2, and NetworkManager 1.58.1. Older Omarchy versions without the Quickshell plugin API are not supported.
