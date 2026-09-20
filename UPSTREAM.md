# Upstream attribution

`Panel.qml` and `Model.js` derive from the Network plugin (`omarchy.network`) shipped with Omarchy `4.0.4-1`:

- https://github.com/omacom/omarchy/tree/quattro/shell/plugins/panels/network
- https://github.com/omacom/omarchy/blob/quattro/LICENSE

Omarchy is copyright David Heinemeier Hansson and distributed under the MIT license. The original notice and permission terms are retained in this repository's LICENSE, with an additional notice for Daniele Galdi's modifications.

Network adds the password visibility toggle, camera-only QR joining, detection feedback, a distinct plugin/IPC namespace, and publication documentation. It uses the installed Omarchy `qs.Ui` and `qs.Commons` components; these shared components are not copied into the repository.

The published manifest intentionally has no `omarchy.clonedFrom` field. Enabling or removing Network therefore does not silently replace or restore another widget. Installation/removal commands in the README make that choice explicit.

This is an independent plugin, not an official Omarchy plugin. Updates to Omarchy's Network plugin are not automatically merged; review upstream changes when maintaining compatibility.
