#include "olympus_panel.h"

#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/object/callable_mp.h"
#include "core/os/os.h"
#include "core/os/time.h"
#include "editor/file_system/editor_paths.h"
#include "editor/settings/editor_settings.h"
#include "scene/gui/button.h"
#include "scene/gui/label.h"
#include "scene/gui/line_edit.h"
#include "scene/gui/text_edit.h"
#include "scene/main/timer.h"

OlympusPanel::OlympusPanel() {
    set_name("OlympusPage");
    EDITOR_DEF("olympus/workspace", OS::get_singleton()->get_environment("OLYMPUS_WORKSPACE"));
    EDITOR_DEF("olympus/python", OS::get_singleton()->get_environment("OLYMPUS_PYTHON"));
    EDITOR_DEF("olympus/tenant", "olympus-workspace");
    Label *notice = memnew(Label);
    notice->set_text(U"Olympus · 框架与赫尔墨斯数据\n接入检查不代表 Agent 已获准启用。配置保存于本机编辑器设置。");
    notice->set_autowrap_mode(TextServer::AUTOWRAP_WORD_SMART);
    add_child(notice);
    workspace = memnew(LineEdit);
    workspace->set_placeholder(U"Olympus 工作区根目录");
    workspace->set_text(EDITOR_GET("olympus/workspace"));
    add_child(workspace);
    python = memnew(LineEdit);
    python->set_placeholder(U"Python 可执行文件路径");
    python->set_text(EDITOR_GET("olympus/python"));
    add_child(python);
    tenant = memnew(LineEdit);
    tenant->set_placeholder(U"数据租户");
    tenant->set_text(EDITOR_GET("olympus/tenant"));
    add_child(tenant);
    const char *actions[] = {"status", "check", "validate", "analyze"};
    const String labels[] = {U"读取框架状态", U"核对上游及候选完整性", U"校验赫尔墨斯数据", U"分析当前租户记录"};
    for (int i = 0; i < 4; i++) {
        Button *button = memnew(Button);
        button->set_text(labels[i]);
        button->connect("pressed", callable_mp(this, &OlympusPanel::run_action).bind(String(actions[i])));
        add_child(button);
    }
    output = memnew(TextEdit);
    output->set_name("OlympusOutput");
    output->set_editable(false);
    output->set_v_size_flags(SIZE_EXPAND_FILL);
    add_child(output);
    timer = memnew(Timer);
    timer->set_wait_time(0.25);
    timer->connect("timeout", callable_mp(this, &OlympusPanel::poll));
    add_child(timer);
}

void OlympusPanel::run_action(const String &p_action) {
    if (worker >= 0) {
        return;
    }
    const String script = OS::get_singleton()->get_executable_path().get_base_dir().get_base_dir().path_join("tools/olympus_bridge.py");
    if (workspace->get_text().is_empty() || python->get_text().is_empty() || !FileAccess::exists(script)) {
        output->set_text(U"请填写工作区、Python 路径，并确认引擎 tools/olympus_bridge.py 已安装。");
        return;
    }
    EditorSettings::get_singleton()->set("olympus/workspace", workspace->get_text());
    EditorSettings::get_singleton()->set("olympus/python", python->get_text());
    EditorSettings::get_singleton()->set("olympus/tenant", tenant->get_text());
    result_path = EditorPaths::get_singleton()->get_cache_dir().path_join("olympus-" + itos(OS::get_singleton()->get_process_id()) + "-" + itos(Time::get_singleton()->get_ticks_usec()) + ".json");
    List<String> args;
    args.push_back(script);
    args.push_back(p_action);
    args.push_back("--workspace");
    args.push_back(workspace->get_text());
    args.push_back("--tenant");
    args.push_back(tenant->get_text());
    args.push_back("--out");
    args.push_back(result_path);
    ProcessID pid = 0;
    Error error = OS::get_singleton()->create_process(python->get_text(), args, &pid);
    if (error != OK) {
        output->set_text(U"启动失败，请检查 Python 路径。");
        return;
    }
    worker = pid;
    output->set_text(U"正在执行检查…");
    timer->start();
}

void OlympusPanel::poll() {
    if (OS::get_singleton()->is_process_running(worker)) {
        return;
    }
    timer->stop();
    worker = -1;
    if (FileAccess::exists(result_path)) {
        output->set_text(FileAccess::get_file_as_string(result_path));
        DirAccess::remove_absolute(result_path);
    } else {
        output->set_text(U"检查进程未返回结果，请检查 Python 和工作区配置。");
    }
}
