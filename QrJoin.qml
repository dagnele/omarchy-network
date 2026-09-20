import QtQuick
import QtQuick.Layouts
import QtMultimedia
import Quickshell.Io
import qs.Commons
import qs.Ui

Item {
  id: root
  required property var bar
  property bool sessionOpen: false
  property string stage: "starting"
  property string message: ""
  property string networkName: ""
  property string security: ""
  property string scanHint: ""
  readonly property color detectedColor: "#70d39a"
  property string directory: ""
  property bool awaiting: false
  property int generation: 0
  property int cameraIndex: 0
  readonly property bool ready: worker.running && directory !== ""
  implicitHeight: content.implicitHeight
  signal done()
  signal connected()

  function start() {
    generation++
    stage = "starting"
    networkName = ""
    directory = ""
    awaiting = false
    sessionOpen = true
    message = "Starting camera…"
    worker.running = true
    Qt.callLater(function() { backButton.forceActiveFocus() })
  }

  function cancel() {
    sessionOpen = false
    cameraTimeout.stop()
    detectedDelay.stop()
    hintTimeout.stop()
    scanHint = ""
    generation++
    directory = ""
    awaiting = false
    stage = "starting"
    networkName = ""
    worker.running = false
  }

  function send(command) {
    if (!ready || awaiting) return false
    awaiting = true
    worker.write(JSON.stringify(command) + "\n")
    return true
  }

  function back() {
    // Stop the private worker and discard any buffered result or credential.
    cancel()
    root.done()
  }

  function beginCamera() {
    message = ""
    scanHint = ""
    hintTimeout.stop()
    if (mediaDevices.videoInputs.length === 0) {
      stage = "error"
      message = "No camera found. Connect a webcam and try again."
      return
    }
    stage = "camera"
    cameraTimeout.restart()
  }

  function handle(raw) {
    if (!sessionOpen) return
    var result
    try { result = JSON.parse(raw) } catch (e) { return }
    awaiting = false
    if (result.type === "ready") {
      directory = result.directory
      beginCamera()
      return
    }
    if (result.type === "found") {
      networkName = result.ssid
      security = result.security
      message = ""
      scanHint = ""
      stage = "detected"
      detectedDelay.restart()
    } else if (result.type === "invalid" && stage === "camera") {
      scanHint = result.message
      hintTimeout.restart()
    } else if (result.type === "connected") {
      stage = "success"
      message = "Connected to " + networkName
      root.connected()
    } else if (result.type === "error") {
      stage = "error"
      message = result.message
    } else if (result.type === "reset") {
      beginCamera()
    }
  }

  function retry() {
    if (awaiting) return
    stage = "starting"
    message = "Starting camera…"
    networkName = ""
    send({ action: "reset" })
  }

  onStageChanged: {
    if (stage !== "camera") cameraTimeout.stop()
    if (stage !== "detected") detectedDelay.stop()
  }
  Keys.onEscapePressed: back()
  Component.onDestruction: cancel()

  Process {
    id: worker
    command: ["python", "-u", decodeURIComponent(Qt.resolvedUrl("join-qr.py").toString().replace(/^file:\/\//, ""))]
    stdinEnabled: true
    stdout: SplitParser { onRead: function(line) { root.handle(line) } }
    // Backend errors are returned as private, sanitized JSON messages.
    stderr: StdioCollector { }
    onExited: {
      if (root.sessionOpen) {
        root.awaiting = false
        root.directory = ""
        root.stage = "error"
        root.message = "The scanner stopped. Close this panel and try again."
      }
    }
  }

  MediaDevices { id: mediaDevices }
  CaptureSession {
    camera: Camera {
      id: camera
      cameraDevice: mediaDevices.videoInputs.length > 0
        ? mediaDevices.videoInputs[Math.min(root.cameraIndex, mediaDevices.videoInputs.length - 1)]
        : mediaDevices.defaultVideoInput
      active: root.sessionOpen && (root.stage === "camera" || root.stage === "detected")
      onErrorOccurred: function(error, detail) {
        if (root.stage === "camera") {
          root.stage = "error"
          root.message = "Could not open the camera. Check its privacy switch and whether another app is using it."
        }
      }
    }
    videoOutput: video
  }

  Timer {
    id: detectedDelay
    interval: 1000
    onTriggered: if (root.sessionOpen && root.stage === "detected") {
      root.stage = "confirm"
      Qt.callLater(function() { joinButton.forceActiveFocus() })
    }
  }

  Timer {
    id: hintTimeout
    interval: 3000
    onTriggered: root.scanHint = ""
  }

  Timer {
    id: cameraTimeout
    interval: 90000
    onTriggered: if (root.stage === "camera") {
      root.stage = "error"
      root.message = "No Wi-Fi code found yet. Try increasing your phone’s brightness and holding it steady."
    }
  }

  Timer {
    interval: 1100
    repeat: true
    running: camera.active && root.stage === "camera" && root.ready && !root.awaiting
    onTriggered: {
      if (video.sourceRect.width <= 0) return
      root.awaiting = true
      var generation = root.generation
      var path = root.directory + "/frame.png"
      var started = video.grabToImage(function(result) {
        if (!root.sessionOpen || root.generation !== generation) return
        root.awaiting = false
        if (root.stage !== "camera") return
        if (result.saveToFile(path)) root.send({ action: "decode" })
        else {
          root.stage = "error"
          root.message = "Could not read the camera frame. Please try again."
        }
      }, Qt.size(1280, 960))
      if (!started) root.awaiting = false
    }
  }

  component Label: Text {
    textFormat: Text.PlainText
    color: root.bar.foreground
    font.family: root.bar.fontFamily
    font.pixelSize: Style.font.bodySmall
    wrapMode: Text.Wrap
  }

  component Action: Button {
    foreground: root.bar.foreground
    fontFamily: root.bar.fontFamily
    fontSize: Style.font.bodySmall
    focusable: true
    Accessible.role: Accessible.Button
    Accessible.name: text || tooltipText
  }

  Column {
    id: content
    width: parent.width
    spacing: Style.space(12)

    Action {
      id: backButton
      text: "Back"
      iconText: "󰁍"
      tooltipText: "Back to Wi-Fi"
      onClicked: root.back()
    }

    PanelSeparator { width: parent.width; foreground: root.bar.foreground }

    Column {
      visible: root.stage === "camera" || root.stage === "detected"
      width: parent.width
      spacing: Style.space(8)
      Rectangle {
        width: parent.width
        height: width * 0.75
        color: "#111111"
        radius: Style.cornerRadius
        clip: true
        VideoOutput {
          id: video
          anchors.fill: parent
          fillMode: VideoOutput.PreserveAspectFit
          endOfStreamPolicy: VideoOutput.ClearOutput
        }
        Rectangle {
          anchors.centerIn: parent
          width: Math.min(parent.width, parent.height) * 0.78
          height: width
          color: "transparent"
          border.color: root.stage === "detected" ? root.detectedColor : Color.accent
          border.width: root.stage === "detected" ? 4 : 2
          radius: Style.cornerRadius
          Behavior on border.color { ColorAnimation { duration: 140 } }

          Rectangle {
            visible: root.stage === "detected"
            anchors.centerIn: parent
            width: Style.space(54)
            height: width
            radius: width / 2
            color: "#dd101820"
            Text {
              anchors.centerIn: parent
              text: "󰄬"
              color: root.detectedColor
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.display
            }
          }
        }
      }
      Label {
        width: parent.width
        text: root.stage === "detected" ? "Wi-Fi QR code detected"
          : root.scanHint || "Hold your phone’s Wi-Fi QR code inside the frame."
        color: root.stage === "detected" ? root.detectedColor : root.bar.foreground
        opacity: root.stage === "detected" || root.scanHint !== "" ? 1 : 0.7
      }
      Action {
        visible: mediaDevices.videoInputs.length > 1
        width: parent.width
        text: "Switch camera"
        enabled: !root.awaiting && root.stage === "camera"
        onClicked: root.cameraIndex = (root.cameraIndex + 1) % mediaDevices.videoInputs.length
      }
    }

    Column {
      visible: root.stage === "confirm"
      width: parent.width
      spacing: Style.space(12)
      Label {
        width: parent.width
        text: "󰄬  Wi-Fi QR code detected"
        color: root.detectedColor
      }
      Label {
        width: parent.width
        text: root.networkName
        font.pixelSize: Style.font.title
        font.bold: true
        wrapMode: Text.WrapAnywhere
      }
      Label {
        width: parent.width
        text: root.security === "NOPASS" ? "Open network · no password" : "Password protected · credentials read from QR code"
        opacity: 0.7
      }
      RowLayout {
        width: parent.width
        Action {
          Layout.fillWidth: true
          text: "Scan again"
          onClicked: root.retry()
        }
        Action {
          id: joinButton
          Layout.fillWidth: true
          text: "Join"
          iconText: "󰄬"
          bordered: true
          enabled: root.ready && !root.awaiting
          onClicked: {
            root.stage = "joining"
            root.message = "Connecting to " + root.networkName + "…"
            root.send({ action: "connect" })
          }
        }
      }
    }

    Label {
      width: parent.width
      visible: root.message !== ""
      text: root.message
      color: root.stage === "error" ? root.bar.urgent : root.bar.foreground
    }
    Action {
      width: parent.width
      visible: root.stage === "error"
      text: "Try again"
      enabled: root.ready && !root.awaiting
      onClicked: root.retry()
    }
    Action {
      width: parent.width
      visible: root.stage === "success"
      text: "Done"
      iconText: "󰄬"
      onClicked: root.back()
    }
  }
}
