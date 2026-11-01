#ifndef OLYMPUS_HOST_PATHS_H
#define OLYMPUS_HOST_PATHS_H

#include "core/io/file_access.h"
#include "core/os/os.h"

// Resolve from the installed executable, independently of the current directory.
class OlympusHostPaths {
public:
	static String find_ancestor(String directory, const String &marker) {
		while (!directory.is_empty()) {
			if (FileAccess::exists(directory.path_join(marker))) {
				return directory;
			}
			const String parent = directory.get_base_dir();
			if (parent == directory) {
				break;
			}
			directory = parent;
		}
		return String();
	}

	static String workspace() {
		const String configured = OS::get_singleton()->get_environment("OLYMPUS_WORKSPACE");
		if (!configured.is_empty()) {
			return configured;
		}
		const String executable_dir = OS::get_singleton()->get_executable_path().get_base_dir();
		const String ancestor = find_ancestor(executable_dir, "olympus-workspace.json");
		if (!ancestor.is_empty()) {
			return ancestor;
		}
		const String sibling = executable_dir.get_base_dir().get_base_dir().path_join("Olympus");
		return FileAccess::exists(sibling.path_join("olympus-workspace.json")) ? sibling : String();
	}
};

#endif
