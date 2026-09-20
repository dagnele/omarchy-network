# Release and marketplace submission

Repository name: `dagnele/omarchy-network`  
Plugin ID: `dagnele.network`  
Display name: Network  
Author: Daniele Galdi

## Prepare

1. Run `./tools/check.sh` on Omarchy.
2. Review the diff and update `manifest.json` and `CHANGELOG.md` for the release.
3. Test enable, click/open, Escape, explicit shell open/close, disable, re-enable, shell restart, and removal on the supported Omarchy version.
4. Test the eye toggle, QR scanning while disconnected, an unrelated QR code, scanning cancellation, the green detection cue, and confirmation. Confirm the camera stops on Back and close. Use your own test network to verify an actual join, cancellation during joining, and an incorrect password.
5. Check dependency instructions and shared QR/speed-test actions. Do not embed real Wi-Fi credentials or camera images in preview assets.

`qmllint -I "$OMARCHY_PATH/shell" Panel.qml QrJoin.qml` may not resolve Quickshell's virtual `qs.*` imports outside the running shell. A tooling import root containing `qs/Ui` and `qs/Commons` mapped to the installed shell directories resolves those modules. Remaining warnings about dynamically injected bar/style properties and Quickshell's `QProcess::ExitStatus` are tooling limitations on the tested release; QML parsing and an actual host load are checked separately. Do not interpret a manifest validation result as a full runtime test.

## Publish the source

The prepared project is local. Create the public GitHub repository only when ready to publish. Review the files and commit any further changes first. The initial release is already committed in the prepared local Git repository. If you extracted the ZIP instead, first run `git init -b main`, `git add .`, and `git commit -m "Prepare Network 1.0.0"`.

```sh
gh repo create dagnele/omarchy-network --public --source=. --remote=origin --push
git tag v1.0.0
git push origin v1.0.0
git -C ~/.config/omarchy/plugins/dagnele.network remote set-url origin https://github.com/dagnele/omarchy-network.git
```

These commands require your own Git identity and GitHub authentication. If the repository already exists, set its remote and push instead of creating it again.

## Submit the listing

Read the current [publishing guide](https://plugins.omarchy.org/publish.html), then open the [marketplace submission form](https://github.com/omacom/omarchy-plugin-marketplace/issues/new?template=submit-plugin.yml).

Suggested form values:

- Repository URL: `https://github.com/dagnele/omarchy-network`
- Category: **System**
- Tags: **Bar**, **Quickshell**, **System**
- Maintainer notes: see [MARKETPLACE.md](MARKETPLACE.md).

Confirm the form's checklist only after the repository is public and you have reviewed its contents. Marketplace acceptance is a maintainer decision, not a result of local validation.
