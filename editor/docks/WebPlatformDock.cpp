/**************************************************************************/
/*  WebPlatformDock.cpp                                                   */
/**************************************************************************/
/*                         This file is part of:                          */
/*                             GODOT ENGINE                               */
/*                        https://godotengine.org                         */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md). */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                  */
/*                                                                        */
/* Permission is hereby granted, free of charge, to any person obtaining  */
/* a copy of this software and associated documentation files (the        */
/* "Software"), to deal in the Software without restriction, including    */
/* without limitation the rights to use, copy, modify, merge, publish,    */
/* distribute, sublicense, and/or sell copies of the Software, and to     */
/* permit persons to whom the Software is furnished to do so, subject to  */
/* the following conditions:                                              */
/*                                                                        */
/* The above copyright notice and this permission notice shall be         */
/* included in all copies or substantial portions of the Software.        */
/*                                                                        */
/* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,        */
/* EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF     */
/* MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. */
/* IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY   */
/* CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,   */
/* TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE      */
/* SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.                 */
/**************************************************************************/

#include "WebPlatformDock.h"

#include "editor/docks/WebPlatformNative.h"

#include "core/object/callable_mp.h"
#include "editor/docks/editor_dock.h"
#include "editor/settings/editor_settings.h"
#include "scene/gui/button.h"
#include "scene/gui/label.h"
#include "scene/gui/line_edit.h"
#include "scene/main/window.h"
#include "servers/display/display_server.h"

void WebPlatformDock::_bind_methods()
{
}

void WebPlatformDock::DestroySurface()
{
	delete pNative;
	pNative = nullptr;
}

void WebPlatformDock::ConnectSite()
{
	const String strUrl = pAddress->get_text().strip_edges();
	std::string strOrigin;
	if (!ParseWebPlatformOrigin(strUrl.utf8().get_data(), strOrigin) || strUrl.contains("?") || strUrl.contains("#"))
	{
		strInputError = U"请输入 HTTPS 工作台地址，或本机 HTTP 地址；不要包含账号、密码或登录参数。";
		pStatus->set_text(strInputError);
		return;
	}
	strInputError = String();
	bAttempted = false;
	DestroySurface();
	strConnection = strUrl;
	EditorSettings::get_singleton()->set("network/web_platform/url", strConnection);
	EditorSettings::get_singleton()->save();
	UpdateSurface();
}

void WebPlatformDock::SubmitAddress(const String &)
{
	ConnectSite();
}

void WebPlatformDock::Back()
{
	if (pNative != nullptr)
	{
		pNative->Back();
	}
}

void WebPlatformDock::Forward()
{
	if (pNative != nullptr)
	{
		pNative->Forward();
	}
}

void WebPlatformDock::Reload()
{
	if (pNative != nullptr)
	{
		pNative->Reload();
	}
	else
	{
		ConnectSite();
	}
}

void WebPlatformDock::UpdateSurface()
{
	if (!is_inside_tree())
	{
		return;
	}
	Window *pWindow = get_window();
	bool bVisible = is_visible_in_tree() && pWindow->is_visible() && pWindow->get_exclusive_child() == nullptr;
	const TypedArray<Window> arrPopups = pWindow->get_embedded_subwindows();
	for (int nIndex = 0; nIndex < arrPopups.size(); ++nIndex)
	{
		Window *pPopup = Object::cast_to<Window>(arrPopups[nIndex]);
		if (pPopup != nullptr && pPopup->is_visible())
		{
			bVisible = false;
		}
	}
	DisplayServer *pDisplay = DisplayServer::get_singleton();
	if (pNative == nullptr && !bAttempted && bVisible && !strConnection.is_empty())
	{
		bAttempted = true;
		if (pDisplay->get_name() == "headless")
		{
			pStatus->set_text(U"后台模式：工作区已就绪，网页视图仅在图形编辑器中加载。");
			return;
		}
		const int64_t nView = pDisplay->window_get_native_handle(DisplayServerEnums::WINDOW_VIEW, pWindow->get_window_id());
		pNative = WebPlatformNative::Create(reinterpret_cast<void *>(nView), strConnection.utf8().get_data());
		if (pNative == nullptr)
		{
			pStatus->set_text(U"此构建尚不支持原生网页视图。当前支持 macOS 编辑器。");
			return;
		}
	}
	if (pNative == nullptr)
	{
		return;
	}
	const Rect2 stRect = pSurface->get_viewport()->get_final_transform().xform(pSurface->get_global_rect());
	const Size2i stWindowSize = pDisplay->window_get_size(pWindow->get_window_id());
	pNative->SetBounds(stRect.position.x, stRect.position.y, stRect.size.x, stRect.size.y, stWindowSize.x, stWindowSize.y);
	pNative->SetVisible(bVisible && stRect.size.x > 0 && stRect.size.y > 0);
	pBack->set_disabled(!pNative->CanGoBack());
	pForward->set_disabled(!pNative->CanGoForward());
	pStatus->set_text(strInputError.is_empty() ? String::utf8(pNative->GetStatus().c_str()) : strInputError);
}

void WebPlatformDock::_notification(int nWhat)
{
	if (nWhat == NOTIFICATION_READY)
	{
		set_process(true);
	}
	else if (nWhat == NOTIFICATION_PROCESS || nWhat == NOTIFICATION_VISIBILITY_CHANGED)
	{
		UpdateSurface();
	}
	else if (nWhat == NOTIFICATION_EXIT_TREE)
	{
		DestroySurface();
	}
}

WebPlatformDock::WebPlatformDock()
{
	set_name("WebPlatformWorkbench");
	set_h_size_flags(SIZE_EXPAND_FILL);
	set_v_size_flags(SIZE_EXPAND_FILL);
	HBoxContainer *pToolbar = memnew(HBoxContainer);
	add_child(pToolbar);
	pBack = memnew(Button);
	pBack->set_text(U"后退");
	pBack->set_disabled(true);
	pBack->connect("pressed", callable_mp(this, &WebPlatformDock::Back));
	pToolbar->add_child(pBack);
	pForward = memnew(Button);
	pForward->set_text(U"前进");
	pForward->set_disabled(true);
	pForward->connect("pressed", callable_mp(this, &WebPlatformDock::Forward));
	pToolbar->add_child(pForward);
	Button *pReload = memnew(Button);
	pReload->set_text(U"刷新 / 重试");
	pReload->connect("pressed", callable_mp(this, &WebPlatformDock::Reload));
	pToolbar->add_child(pReload);
	pAddress = memnew(LineEdit);
	pAddress->set_name("WebPlatformAddress");
	pAddress->set_placeholder(U"天璇工作台地址，例如 https://workspace.example.com");
	pAddress->set_h_size_flags(SIZE_EXPAND_FILL);
	strConnection = EDITOR_DEF("network/web_platform/url", "");
	pAddress->set_text(strConnection);
	pAddress->connect("text_submitted", callable_mp(this, &WebPlatformDock::SubmitAddress));
	pToolbar->add_child(pAddress);
	Button *pConnect = memnew(Button);
	pConnect->set_name("ConnectWebPlatform");
	pConnect->set_text(U"连接");
	pConnect->connect("pressed", callable_mp(this, &WebPlatformDock::ConnectSite));
	pToolbar->add_child(pConnect);
	pStatus = memnew(Label);
	pStatus->set_name("WebPlatformStatus");
	pStatus->set_text(U"连接天璇后，可在此使用文曲、需求、工单、多宝与设置。");
	add_child(pStatus);
	pSurface = memnew(Control);
	pSurface->set_name("WebPlatformSurface");
	pSurface->set_v_size_flags(SIZE_EXPAND_FILL);
	pSurface->set_h_size_flags(SIZE_EXPAND_FILL);
	add_child(pSurface);
}

WebPlatformDock::~WebPlatformDock()
{
	DestroySurface();
}

EditorDock *CreateWebPlatformDock()
{
	EditorDock *pDock = memnew(EditorDock);
	pDock->set_name("WebPlatform");
	pDock->set_title(U"天璇");
	pDock->set_layout_key("WebPlatformMainScreen");
	pDock->set_icon_name("WorldEnvironment");
	pDock->set_available_layouts(EditorDock::DOCK_LAYOUT_MAIN_SCREEN);
	pDock->set_default_slot(EditorDock::DOCK_SLOT_MAIN_SCREEN);
	pDock->add_child(memnew(WebPlatformDock));
	return pDock;
}
