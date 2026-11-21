import Foundation
import XCTest

final class SavePanelTests: XCTestCase {
    // The launcher stages this source alongside the isolated app and project.
    private let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent()

    private func waitForFile(_ name: String, timeout: TimeInterval = 75) throws -> Data {
        let url = root.appendingPathComponent(name)
        let failure = root.appendingPathComponent("failure.json")
        let ready = NSPredicate { _, _ in
            FileManager.default.fileExists(atPath: url.path) || FileManager.default.fileExists(atPath: failure.path)
        }
        let expectation = XCTNSPredicateExpectation(predicate: ready, object: nil)
        XCTAssertEqual(XCTWaiter.wait(for: [expectation], timeout: timeout), .completed, "Waiting for \(name)")
        if let error = try? String(contentsOf: failure, encoding: .utf8) {
            XCTFail(error)
        }
        return try Data(contentsOf: url)
    }

    @MainActor
    func testExportImageMeshAndCancel() throws {
        continueAfterFailure = false
        let app = XCUIApplication(url: root.appendingPathComponent("Godot.app"))
        let config = try Data(contentsOf: root.appendingPathComponent("environment.json"))
        app.launchEnvironment = try JSONDecoder().decode([String: String].self, from: config)
        app.launchArguments = ["--editor", "--path", root.appendingPathComponent("project").path,
                               "--script", "res://probe.gd", "--log-file", root.appendingPathComponent("editor.log").path]
        app.launch()
        defer { app.terminate() }
        let destination = root.appendingPathComponent("exports")
        for step in ["image", "mesh", "cancel"] {
            try XCTContext.runActivity(named: step) { activity in
                let marker = try JSONDecoder().decode([String: String].self, from: waitForFile(step + ".json"))
                let suggested = try XCTUnwrap(marker["suggested_name"])
                let stem = (suggested as NSString).deletingPathExtension
                let panel = app.sheets["save-panel"]
                XCTAssertTrue(panel.waitForExistence(timeout: 15), app.debugDescription)
                let filename = panel.textFields["saveAsNameTextField"]
                XCTAssertTrue(filename.waitForExistence(timeout: 10))
                let displayed = try XCTUnwrap(filename.value as? String)
                XCTAssertTrue(displayed == suggested || displayed == stem, "Unexpected suggested name: \(displayed)")

                if step != "cancel" {
                    app.typeKey("g", modifierFlags: [.command, .shift])
                    app.typeKey("a", modifierFlags: .command)
                    app.typeText(destination.path)
                    app.typeKey(.return, modifierFlags: [])
                    let location = panel.popUpButtons["where popup"]
                    if location.exists {
                        let expected = NSPredicate(format: "value == %@", destination.lastPathComponent)
                        let ready = XCTNSPredicateExpectation(predicate: expected, object: location)
                        XCTAssertEqual(XCTWaiter.wait(for: [ready], timeout: 12), .completed, panel.debugDescription)
                    }
                }

                // The sheet contains the AppKit button. The Touch Bar exposes separate
                // controls with the same titles outside the sheet.
                let button = panel.buttons[step == "cancel" ? "CancelButton" : "OKButton"]
                XCTAssertTrue(button.waitForExistence(timeout: 10), panel.debugDescription)
                let screenshot = XCTAttachment(screenshot: app.screenshot())
                screenshot.name = "\(step)-native-save-panel"
                screenshot.lifetime = .keepAlways
                activity.add(screenshot)
                if button.isHittable {
                    button.click()
                } else {
                    app.typeKey(step == "cancel" ? .escape : .return, modifierFlags: [])
                }
            }
        }
        _ = try waitForFile("callbacks.json")
    }
}
