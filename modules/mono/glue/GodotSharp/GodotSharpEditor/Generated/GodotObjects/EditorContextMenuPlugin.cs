namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para><see cref="Godot.EditorContextMenuPlugin"/> allows for the addition of custom options in the editor's context menu. Register them with <see cref="Godot.EditorPlugin.AddContextMenuPlugin(EditorContextMenuPlugin.ContextMenuSlot, EditorContextMenuPlugin)"/>.</para>
/// <para>See <see cref="Godot.EditorContextMenuPlugin.ContextMenuSlot"/> for the list of available areas where context menu plugins are supported.</para>
/// </summary>
public partial class EditorContextMenuPlugin : RefCounted
{
    public enum ContextMenuSlot : long
    {
        /// <summary>
        /// <para>Context menu of Scene dock. The data <see cref="Godot.Collections.Dictionary"/> contains:</para>
        /// <para><c>&amp;"selected_nodes": Array[Node]</c> - The list of currently selected nodes (same as <see cref="Godot.EditorSelection.GetTopSelectedNodes()"/>).</para>
        /// </summary>
        SceneTree = 0,
        /// <summary>
        /// <para>Context menu of FileSystem dock. The data <see cref="Godot.Collections.Dictionary"/> contains:</para>
        /// <para><c>&amp;"selected_files": PackedStringArray</c> - The list of selected files.</para>
        /// </summary>
        Filesystem = 1,
        /// <summary>
        /// <para>Context menu of Script editor's script tabs and Shader editor's shader tabs. The data <see cref="Godot.Collections.Dictionary"/> contains:</para>
        /// <para><c>&amp;"selected_resource": Resource</c> - The currently selected resource. Can be a <see cref="Godot.Script"/>, a <see cref="Godot.Shader"/>, a text file, or <see langword="null"/> in case of help pages.</para>
        /// <para><c>&amp;"path": String</c> - The path of the selected file. If a help page is selected, the path will be the name of the opened class, prefixed with <c>help:</c>.</para>
        /// </summary>
        ScriptEditor = 2,
        /// <summary>
        /// <para>The "Create..." submenu of FileSystem dock's context menu, or the "New" section of the main context menu when empty space is clicked. The data <see cref="Godot.Collections.Dictionary"/> contains:</para>
        /// <para><c>&amp;"base_directory": String</c> - Path to the base directory where a file should be created.</para>
        /// <para><c>&amp;"needs_prefix": bool</c> - Whether the option needs a "New" prefix (for consistency with native options).</para>
        /// <para><code>
        /// func _get_menu_options(data):
        /// 	if data["needs_prefix"]:
        /// 		add_context_menu_item("New Image File...", create_image)
        /// 	else:
        /// 		add_context_menu_item("Image File...", create_image)
        /// </code></para>
        /// </summary>
        FilesystemCreate = 3,
        /// <summary>
        /// <para>Context menu of Script editor's code editor. The data <see cref="Godot.Collections.Dictionary"/> contains:</para>
        /// <para><c>&amp;"code_edit": CodeEdit</c> - The code editor instance.</para>
        /// <para><c>&amp;"file_path": String</c> - Path to the currently edited file.</para>
        /// </summary>
        ScriptEditorCode = 4,
        /// <summary>
        /// <para>Context menu of scene tabs. The data <see cref="Godot.Collections.Dictionary"/> contains:</para>
        /// <para><c>&amp;"selected_scene": String</c> - Scene path of the selected/clicked scene tab. Empty if empty space was clicked.</para>
        /// </summary>
        SceneTabs = 5,
        /// <summary>
        /// <para>Context menu of the 2D editor's viewport. The data <see cref="Godot.Collections.Dictionary"/> contains:</para>
        /// <para><c>&amp;"hovered_nodes": Array[CanvasItem]</c> - The <see cref="Godot.CanvasItem"/> nodes under the cursor.</para>
        /// <para><c>&amp;"mouse_position": Vector2</c> - The local mouse position in the 2D scene.</para>
        /// </summary>
        Slot2DEditor = 6,
        /// <summary>
        /// <para>Context menu of an editor property in the inspector. The data <see cref="Godot.Collections.Dictionary"/> contains:</para>
        /// <para><c>&amp;"property": EditorProperty</c> - The clicked <see cref="Godot.EditorProperty"/> object.</para>
        /// <para><c>&amp;"object": Object</c> - The object edited by the inspector.</para>
        /// <para><c>&amp;"property_name": StringName</c> - The name of the object's property that was clicked.</para>
        /// </summary>
        InspectorProperty = 7
    }

    private static readonly System.Type CachedType = typeof(EditorContextMenuPlugin);

    private static readonly StringName NativeName = "EditorContextMenuPlugin";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public EditorContextMenuPlugin() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal EditorContextMenuPlugin(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal EditorContextMenuPlugin(bool memoryOwn) : base(memoryOwn) { }

    /// <summary>
    /// <para>Called when creating a context menu, custom options can be added by using the <see cref="Godot.EditorContextMenuPlugin.AddContextMenuItem(string, Callable, Texture2D)"/> or <see cref="Godot.EditorContextMenuPlugin.AddContextMenuItemFromShortcut(string, Shortcut, Texture2D)"/> functions. <paramref name="data"/> contains the context data, which differs depending on the context menu slot. See the descriptions of <see cref="Godot.EditorContextMenuPlugin.ContextMenuSlot"/> for more information.</para>
    /// </summary>
    public virtual void _GetMenuOptions(Godot.Collections.Dictionary<StringName, Variant> data)
    {
    }

    /// <summary>
    /// <para><b>Note:</b> Implementing this method makes the shortcut callbacks receive legacy data (for compatibility reasons).</para>
    /// </summary>
    [Obsolete("Use 'Godot.EditorContextMenuPlugin._GetMenuOptions(Godot.Collections.Dictionary<StringName, Variant>)' instead.")]
    public virtual void _PopupMenu(string[] paths)
    {
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.AddMenuShortcut, 851596305ul);

    /// <summary>
    /// <para>Registers a shortcut associated with the plugin's context menu. This method should be called once (e.g. in the plugin's <see cref="Godot.GodotObject.GodotObject()"/>). <paramref name="callback"/> will be called when user presses the specified <paramref name="shortcut"/> while the menu's context is in effect (e.g. FileSystem dock is focused). Callback should take single data <see cref="Godot.Collections.Dictionary"/>, same as in <see cref="Godot.EditorContextMenuPlugin.AddContextMenuItem(string, Callable, Texture2D)"/>.</para>
    /// <para><code>
    /// func _init():
    /// 	add_menu_shortcut(SHORTCUT, handle)
    /// </code></para>
    /// </summary>
    public void AddMenuShortcut(Shortcut shortcut, Callable callback)
    {
        EditorNativeCalls.godot_icall_2_479(MethodBind0, GodotObject.GetPtr(this), GodotObject.GetPtr(shortcut), callback);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.AddContextMenuItem, 2748336951ul);

    /// <summary>
    /// <para>Add custom option to the context menu of the plugin's specified slot. <paramref name="callback"/> should be a method that takes a single argument of type <see cref="Godot.Collections.Dictionary"/>. It will be called when the option is activated and the data received in the callback is the same as in <see cref="Godot.EditorContextMenuPlugin._GetMenuOptions(Godot.Collections.Dictionary{StringName, Variant})"/>.</para>
    /// <para><code>
    /// func _get_menu_options(data):
    /// 	add_context_menu_item("File Custom options", handle, ICON)
    /// </code></para>
    /// <para>If you want to assign shortcut to the menu item, use <see cref="Godot.EditorContextMenuPlugin.AddContextMenuItemFromShortcut(string, Shortcut, Texture2D)"/> instead.</para>
    /// </summary>
    public void AddContextMenuItem(string name, Callable callback, Texture2D icon = null)
    {
        EditorNativeCalls.godot_icall_3_480(MethodBind1, GodotObject.GetPtr(this), name, callback, GodotObject.GetPtr(icon));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.AddContextMenuItemFromShortcut, 3799546916ul);

    /// <summary>
    /// <para>Add custom option to the context menu of the plugin's specified slot. The option will have the <paramref name="shortcut"/> assigned and reuse its callback. The shortcut has to be registered beforehand with <see cref="Godot.EditorContextMenuPlugin.AddMenuShortcut(Shortcut, Callable)"/>.</para>
    /// <para><code>
    /// func _init():
    /// 	add_menu_shortcut(SHORTCUT, handle)
    /// 
    /// func _get_menu_options(paths):
    /// 	add_context_menu_item_from_shortcut("File Custom options", SHORTCUT, ICON)
    /// </code></para>
    /// </summary>
    public void AddContextMenuItemFromShortcut(string name, Shortcut shortcut, Texture2D icon = null)
    {
        EditorNativeCalls.godot_icall_3_481(MethodBind2, GodotObject.GetPtr(this), name, GodotObject.GetPtr(shortcut), GodotObject.GetPtr(icon));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.AddContextSubmenuItem, 1994674995ul);

    /// <summary>
    /// <para>Add a submenu to the context menu of the plugin's specified slot. The submenu is not automatically handled, you need to connect to its signals yourself. Also the submenu is freed on every popup, so provide a new <see cref="Godot.PopupMenu"/> every time.</para>
    /// <para><code>
    /// func _get_menu_options(data):
    /// 	var popup_menu = PopupMenu.new()
    /// 	popup_menu.add_item("Blue")
    /// 	popup_menu.add_item("White")
    /// 	popup_menu.id_pressed.connect(_on_color_submenu_option)
    /// 
    /// 	add_context_submenu_item("Set Node Color", popup_menu)
    /// </code></para>
    /// </summary>
    public void AddContextSubmenuItem(string name, PopupMenu menu, Texture2D icon = null)
    {
        EditorNativeCalls.godot_icall_3_481(MethodBind3, GodotObject.GetPtr(this), name, GodotObject.GetPtr(menu), GodotObject.GetPtr(icon));
        global::System.GC.KeepAlive(this);
    }

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName MethodProxyName__get_menu_options = "_GetMenuOptions";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName MethodProxyName__popup_menu = "_PopupMenu";

    /// <summary>
    /// Invokes the method with the given name, using the given arguments.
    /// This method is used by Godot to invoke methods from the engine side.
    /// Do not call or override this method.
    /// </summary>
    /// <param name="method">Name of the method to invoke.</param>
    /// <param name="args">Arguments to use with the invoked method.</param>
    /// <param name="ret">Value returned by the invoked method.</param>
#pragma warning disable CS0618 // Member is obsolete
    protected internal override bool InvokeGodotClassMethod(in godot_string_name method, NativeVariantPtrArgs args, out godot_variant ret)
    {
        if ((method == MethodProxyName__get_menu_options || method == MethodName._GetMenuOptions) && args.Count == 1 && HasGodotClassMethod((godot_string_name)MethodProxyName__get_menu_options.NativeValue))
        {
            _GetMenuOptions(new Godot.Collections.Dictionary<StringName, Variant>(VariantUtils.ConvertToDictionary(args[0])));
            ret = default;
            return true;
        }
        if ((method == MethodProxyName__popup_menu || method == MethodName._PopupMenu) && args.Count == 1 && HasGodotClassMethod((godot_string_name)MethodProxyName__popup_menu.NativeValue))
        {
            _PopupMenu(VariantUtils.ConvertTo<string[]>(args[0]));
            ret = default;
            return true;
        }
        return base.InvokeGodotClassMethod(method, args, out ret);
    }
#pragma warning restore CS0618

    /// <summary>
    /// Check if the type contains a method with the given name.
    /// This method is used by Godot to check if a method exists before invoking it.
    /// Do not call or override this method.
    /// </summary>
    /// <param name="method">Name of the method to check for.</param>

    protected internal override bool HasGodotClassMethod(in godot_string_name method)
    {
        if (method == MethodName._GetMenuOptions)
        {
            if (HasGodotClassMethod(MethodProxyName__get_menu_options.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (method == MethodName._PopupMenu)
        {
            if (HasGodotClassMethod(MethodProxyName__popup_menu.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        return base.HasGodotClassMethod(method);
    }

    /// <summary>
    /// Check if the type contains a signal with the given name.
    /// This method is used by Godot to check if a signal exists before raising it.
    /// Do not call or override this method.
    /// </summary>
    /// <param name="signal">Name of the signal to check for.</param>

    protected internal override bool HasGodotClassSignal(in godot_string_name signal)
    {
        return base.HasGodotClassSignal(signal);
    }

    /// <summary>
    /// Cached StringNames for the properties and fields contained in this class, for fast lookup.
    /// </summary>
    public new class PropertyName : RefCounted.PropertyName
    {
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : RefCounted.MethodName
    {
        /// <summary>
        /// Cached name for the '_get_menu_options' method.
        /// </summary>
        public static readonly StringName _GetMenuOptions = "_get_menu_options";
        /// <summary>
        /// Cached name for the '_popup_menu' method.
        /// </summary>
        public static readonly StringName _PopupMenu = "_popup_menu";
        /// <summary>
        /// Cached name for the 'add_menu_shortcut' method.
        /// </summary>
        public static readonly StringName AddMenuShortcut = "add_menu_shortcut";
        /// <summary>
        /// Cached name for the 'add_context_menu_item' method.
        /// </summary>
        public static readonly StringName AddContextMenuItem = "add_context_menu_item";
        /// <summary>
        /// Cached name for the 'add_context_menu_item_from_shortcut' method.
        /// </summary>
        public static readonly StringName AddContextMenuItemFromShortcut = "add_context_menu_item_from_shortcut";
        /// <summary>
        /// Cached name for the 'add_context_submenu_item' method.
        /// </summary>
        public static readonly StringName AddContextSubmenuItem = "add_context_submenu_item";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : RefCounted.SignalName
    {
    }
}
