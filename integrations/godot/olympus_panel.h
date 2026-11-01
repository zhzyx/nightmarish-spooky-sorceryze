#pragma once

#include "scene/gui/box_container.h"

class LineEdit;
class TextEdit;
class Timer;

class OlympusPanel : public VBoxContainer {
    LineEdit *workspace = nullptr;
    LineEdit *python = nullptr;
    LineEdit *tenant = nullptr;
    TextEdit *output = nullptr;
    Timer *timer = nullptr;
    int64_t worker = -1;
    String result_path;
    void run_action(const String &p_action);
    void poll();

public:
    OlympusPanel();
};
