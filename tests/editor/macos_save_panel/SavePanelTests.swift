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
        for (step, name) in [("image", "chosen-image"), ("mesh", "chosen-mesh"), ("cancel", "cancelled")] {
            try XCTContext.runActivity(named: step) { activity in
                let marker = try JSONDecoder().decode([String: String].self, from: waitForFile(step + ".json"))
                let suggested = try XCTUnwrap(marker["suggested_name"])
                let stem = (suggested as NSString).deletingPathExtension
                // AppKit may hide the extension in the editable field.
                let nameField = app.textFields.matching(NSPredicate(format: "value == %@ OR value == %@", suggested, stem)).firstMatch
                XCTAssertTrue(nameField.waitForExistence(timeout: 15), app.debugDescription)
                let includesExtension = nameField.value as? String == suggested
                nameField.click()
                app.typeKey("a", modifierFlags: .command)
                let fileExtension = (suggested as NSString).pathExtension
                app.typeText(includesExtension ? "\(name).\(fileExtension)" : name)

                // Choose a folder outside the project using the system Go to Folder sheet.
                app.typeKey("g", modifierFlags: [.command, .shift])
                app.typeKey("a", modifierFlags: .command)
                app.typeText(destination.path)
                app.typeKey(.return, modifierFlags: [])

                let action = app.buttons[step == "cancel" ? "Cancel" : "Save"].firstMatch
                XCTAssertTrue(action.waitForExistence(timeout: 10), app.debugDescription)
                XCTAssertTrue(action.isHittable && action.isEnabled, app.debugDescription)
                let screenshot = XCTAttachment(screenshot: app.screenshot())
                screenshot.name = "\(step)-before-\(action.label)"
                screenshot.lifetime = .keepAlways
                activity.add(screenshot)
                action.click()
            }
        }
        _ = try waitForFile("callbacks.json")
    }
}
