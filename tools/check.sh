#!/usr/bin/env bash
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
omarchy plugin validate "$repo_dir"
qml_formatter=$(command -v qmlformat || true)
if [[ -z $qml_formatter && -x /usr/lib/qt6/bin/qmlformat ]]; then
  qml_formatter=/usr/lib/qt6/bin/qmlformat
fi
[[ -n $qml_formatter ]] || { echo 'qmlformat is required (qt6-declarative).' >&2; exit 1; }
"$qml_formatter" --ignore-settings "$repo_dir/Panel.qml" "$repo_dir/QrJoin.qml" >/dev/null
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s "$repo_dir/tests" -v
