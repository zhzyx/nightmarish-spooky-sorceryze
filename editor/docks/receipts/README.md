# Ordinary game receipt guard

This native unit belongs to the existing Godot host receipt lifecycle (Issue #948).
All paths in the build-impact evidence resolve from the repository root.

`AIChatDock::GetGameReceiptGuard` runs on the editor main thread at the existing
command, flush and recovery boundaries. It reads the current workflow root and
host-validated reporting scope, invokes the trusted installed Python guard, and
returns either the verified command guard descriptor or an error. It does not
create an engine candidate, grant authority, replay a command or own UI objects.
The synchronous call introduces no callback or retained pointer lifetime.

`../SCsub` explicitly includes `receipts/*.cpp`; changing this unit or its host
class declaration changes native build inputs. `.clang-format` inherits the
repository policy and changes block layout only within this new unit to satisfy
the project C++ standard. Legacy files retain their existing format.

Rollback uses the previous verified editor and matching trusted host tools while
retaining private receipt bindings, journals, event history and user projects.
This is native code, not an independently replaceable runtime package.
