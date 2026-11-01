namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para><see cref="Godot.AccessibilityServer"/> handles screen reader support.</para>
/// <para><b>Note:</b> <see cref="Godot.AccessibilityServer"/> is implemented on Android, Linux, macOS, and Windows.</para>
/// </summary>
public static partial class AccessibilityServer
{
    public enum AccessibilityRole : long
    {
        /// <summary>
        /// <para>Unknown or custom role.</para>
        /// </summary>
        Unknown = 0,
        /// <summary>
        /// <para>Default dialog button element.</para>
        /// </summary>
        DefaultButton = 1,
        /// <summary>
        /// <para>Audio player element.</para>
        /// </summary>
        Audio = 2,
        /// <summary>
        /// <para>Video player element.</para>
        /// </summary>
        Video = 3,
        /// <summary>
        /// <para>Non-editable text label.</para>
        /// </summary>
        StaticText = 4,
        /// <summary>
        /// <para>Container element. Elements with this role are used for internal structure and ignored by screen readers.</para>
        /// </summary>
        Container = 5,
        /// <summary>
        /// <para>Panel container element.</para>
        /// </summary>
        Panel = 6,
        /// <summary>
        /// <para>Button element.</para>
        /// </summary>
        Button = 7,
        /// <summary>
        /// <para>Link element.</para>
        /// </summary>
        Link = 8,
        /// <summary>
        /// <para>Check box element.</para>
        /// </summary>
        CheckBox = 9,
        /// <summary>
        /// <para>Radio button element.</para>
        /// </summary>
        RadioButton = 10,
        /// <summary>
        /// <para>Check button element.</para>
        /// </summary>
        CheckButton = 11,
        /// <summary>
        /// <para>Scroll bar element.</para>
        /// </summary>
        ScrollBar = 12,
        /// <summary>
        /// <para>Scroll container element.</para>
        /// </summary>
        ScrollView = 13,
        /// <summary>
        /// <para>Container splitter handle element.</para>
        /// </summary>
        Splitter = 14,
        /// <summary>
        /// <para>Slider element.</para>
        /// </summary>
        Slider = 15,
        /// <summary>
        /// <para>Spin box element.</para>
        /// </summary>
        SpinButton = 16,
        /// <summary>
        /// <para>Progress indicator element.</para>
        /// </summary>
        ProgressIndicator = 17,
        /// <summary>
        /// <para>Editable text field element.</para>
        /// </summary>
        TextField = 18,
        /// <summary>
        /// <para>Multiline editable text field element.</para>
        /// </summary>
        MultilineTextField = 19,
        /// <summary>
        /// <para>Color picker element.</para>
        /// </summary>
        ColorPicker = 20,
        /// <summary>
        /// <para>Table element.</para>
        /// </summary>
        Table = 21,
        /// <summary>
        /// <para>Table/tree cell element.</para>
        /// </summary>
        Cell = 22,
        /// <summary>
        /// <para>Table/tree row element.</para>
        /// </summary>
        Row = 23,
        /// <summary>
        /// <para>Table/tree row group element.</para>
        /// </summary>
        RowGroup = 24,
        /// <summary>
        /// <para>Table/tree row header element.</para>
        /// </summary>
        RowHeader = 25,
        /// <summary>
        /// <para>Table/tree column header element.</para>
        /// </summary>
        ColumnHeader = 26,
        /// <summary>
        /// <para>Tree view element.</para>
        /// </summary>
        Tree = 27,
        /// <summary>
        /// <para>Tree view item element.</para>
        /// </summary>
        TreeItem = 28,
        /// <summary>
        /// <para>List element.</para>
        /// </summary>
        List = 29,
        /// <summary>
        /// <para>List item element.</para>
        /// </summary>
        ListItem = 30,
        /// <summary>
        /// <para>List view element.</para>
        /// </summary>
        ListBox = 31,
        /// <summary>
        /// <para>List view item element.</para>
        /// </summary>
        ListBoxOption = 32,
        /// <summary>
        /// <para>Tab bar element.</para>
        /// </summary>
        TabBar = 33,
        /// <summary>
        /// <para>Tab bar item element.</para>
        /// </summary>
        Tab = 34,
        /// <summary>
        /// <para>Tab panel element.</para>
        /// </summary>
        TabPanel = 35,
        /// <summary>
        /// <para>Menu bar element.</para>
        /// </summary>
        MenuBar = 36,
        /// <summary>
        /// <para>Popup menu element.</para>
        /// </summary>
        Menu = 37,
        /// <summary>
        /// <para>Popup menu item element.</para>
        /// </summary>
        MenuItem = 38,
        /// <summary>
        /// <para>Popup menu check button item element.</para>
        /// </summary>
        MenuItemCheckBox = 39,
        /// <summary>
        /// <para>Popup menu radio button item element.</para>
        /// </summary>
        MenuItemRadio = 40,
        /// <summary>
        /// <para>Image element.</para>
        /// </summary>
        Image = 41,
        /// <summary>
        /// <para>Window element.</para>
        /// </summary>
        Window = 42,
        /// <summary>
        /// <para>Embedded window title bar element.</para>
        /// </summary>
        TitleBar = 43,
        /// <summary>
        /// <para>Dialog window element.</para>
        /// </summary>
        Dialog = 44,
        /// <summary>
        /// <para>Tooltip element.</para>
        /// </summary>
        Tooltip = 45,
        /// <summary>
        /// <para>Region/landmark element. Screen readers can navigate between regions using landmark navigation.</para>
        /// </summary>
        Region = 46,
        /// <summary>
        /// <para>Unifor text run.</para>
        /// <para>Note: This role is used for internal text elements, and should not be assigned to nodes.</para>
        /// </summary>
        TextRun = 47
    }

    public enum AccessibilityPopupType : long
    {
        /// <summary>
        /// <para>Popup menu.</para>
        /// </summary>
        Menu = 0,
        /// <summary>
        /// <para>Popup list.</para>
        /// </summary>
        List = 1,
        /// <summary>
        /// <para>Popup tree view.</para>
        /// </summary>
        Tree = 2,
        /// <summary>
        /// <para>Popup dialog.</para>
        /// </summary>
        Dialog = 3
    }

    public enum AccessibilityFlags : long
    {
        /// <summary>
        /// <para>Element is hidden for accessibility tools.</para>
        /// </summary>
        Hidden = 0,
        /// <summary>
        /// <para>Element supports multiple item selection.</para>
        /// </summary>
        Multiselectable = 1,
        /// <summary>
        /// <para>Element require user input.</para>
        /// </summary>
        Required = 2,
        /// <summary>
        /// <para>Element is a visited link.</para>
        /// </summary>
        Visited = 3,
        /// <summary>
        /// <para>Element content is not ready (e.g. loading).</para>
        /// </summary>
        Busy = 4,
        /// <summary>
        /// <para>Element is modal window.</para>
        /// </summary>
        Modal = 5,
        /// <summary>
        /// <para>Element allows touches to be passed through when a screen reader is in touch exploration mode.</para>
        /// </summary>
        TouchPassthrough = 6,
        /// <summary>
        /// <para>Element is text field with selectable but read-only text.</para>
        /// </summary>
        Readonly = 7,
        /// <summary>
        /// <para>Element is disabled.</para>
        /// </summary>
        Disabled = 8,
        /// <summary>
        /// <para>Element clips children.</para>
        /// </summary>
        ClipsChildren = 9
    }

    public enum AccessibilityAction : long
    {
        /// <summary>
        /// <para>Single click action, callback argument is not set.</para>
        /// </summary>
        Click = 0,
        /// <summary>
        /// <para>Focus action, callback argument is not set.</para>
        /// </summary>
        Focus = 1,
        /// <summary>
        /// <para>Blur action, callback argument is not set.</para>
        /// </summary>
        Blur = 2,
        /// <summary>
        /// <para>Collapse action, callback argument is not set.</para>
        /// </summary>
        Collapse = 3,
        /// <summary>
        /// <para>Expand action, callback argument is not set.</para>
        /// </summary>
        Expand = 4,
        /// <summary>
        /// <para>Decrement action, callback argument is not set.</para>
        /// </summary>
        Decrement = 5,
        /// <summary>
        /// <para>Increment action, callback argument is not set.</para>
        /// </summary>
        Increment = 6,
        /// <summary>
        /// <para>Hide tooltip action, callback argument is not set.</para>
        /// </summary>
        HideTooltip = 7,
        /// <summary>
        /// <para>Show tooltip action, callback argument is not set.</para>
        /// </summary>
        ShowTooltip = 8,
        /// <summary>
        /// <para>Set text selection action, callback argument is set to <see cref="Godot.Collections.Dictionary"/> with the following keys:</para>
        /// <para>- <c>"start_element"</c> accessibility element of the selection start.</para>
        /// <para>- <c>"start_char"</c> character offset relative to the accessibility element of the selection start.</para>
        /// <para>- <c>"end_element"</c> accessibility element of the selection end.</para>
        /// <para>- <c>"end_char"</c> character offset relative to the accessibility element of the selection end.</para>
        /// </summary>
        SetTextSelection = 9,
        /// <summary>
        /// <para>Replace text action, callback argument is set to <see cref="string"/> with the replacement text.</para>
        /// </summary>
        ReplaceSelectedText = 10,
        /// <summary>
        /// <para>Scroll backward action, callback argument is not set.</para>
        /// </summary>
        ScrollBackward = 11,
        /// <summary>
        /// <para>Scroll down action, callback argument is set to <see cref="Godot.AccessibilityServer.AccessibilityScrollUnit"/>.</para>
        /// </summary>
        ScrollDown = 12,
        /// <summary>
        /// <para>Scroll forward action, callback argument is not set.</para>
        /// </summary>
        ScrollForward = 13,
        /// <summary>
        /// <para>Scroll left action, callback argument is set to <see cref="Godot.AccessibilityServer.AccessibilityScrollUnit"/>.</para>
        /// </summary>
        ScrollLeft = 14,
        /// <summary>
        /// <para>Scroll right action, callback argument is set to <see cref="Godot.AccessibilityServer.AccessibilityScrollUnit"/>.</para>
        /// </summary>
        ScrollRight = 15,
        /// <summary>
        /// <para>Scroll up action, callback argument is set to <see cref="Godot.AccessibilityServer.AccessibilityScrollUnit"/>.</para>
        /// </summary>
        ScrollUp = 16,
        /// <summary>
        /// <para>Scroll into view action, callback argument is set to <see cref="Godot.AccessibilityServer.AccessibilityScrollHint"/>.</para>
        /// </summary>
        ScrollIntoView = 17,
        /// <summary>
        /// <para>Scroll to point action, callback argument is set to <see cref="Godot.Vector2"/> with the relative point coordinates.</para>
        /// </summary>
        ScrollToPoint = 18,
        /// <summary>
        /// <para>Set scroll offset action, callback argument is set to <see cref="Godot.Vector2"/> with the scroll offset.</para>
        /// </summary>
        SetScrollOffset = 19,
        /// <summary>
        /// <para>Set value action, callback argument is set to <see cref="string"/> or number with the new value.</para>
        /// </summary>
        SetValue = 20,
        /// <summary>
        /// <para>Show context menu action, callback argument is not set.</para>
        /// </summary>
        ShowContextMenu = 21,
        /// <summary>
        /// <para>Custom action, callback argument is set to the integer action ID.</para>
        /// </summary>
        Custom = 22
    }

    public enum AccessibilityLiveMode : long
    {
        /// <summary>
        /// <para>Indicates that updates to the live region should not be presented.</para>
        /// </summary>
        Off = 0,
        /// <summary>
        /// <para>Indicates that updates to the live region should be presented at the next opportunity (for example at the end of speaking the current sentence).</para>
        /// </summary>
        Polite = 1,
        /// <summary>
        /// <para>Indicates that updates to the live region have the highest priority and should be presented immediately.</para>
        /// </summary>
        Assertive = 2
    }

    public enum AccessibilityScrollUnit : long
    {
        /// <summary>
        /// <para>The amount by which to scroll. A single item of a list, line of text.</para>
        /// </summary>
        Item = 0,
        /// <summary>
        /// <para>The amount by which to scroll. A single page.</para>
        /// </summary>
        Page = 1
    }

    public enum AccessibilityScrollHint : long
    {
        /// <summary>
        /// <para>A preferred position for the node scrolled into view. Top-left edge of the scroll container.</para>
        /// </summary>
        TopLeft = 0,
        /// <summary>
        /// <para>A preferred position for the node scrolled into view. Bottom-right edge of the scroll container.</para>
        /// </summary>
        BottomRight = 1,
        /// <summary>
        /// <para>A preferred position for the node scrolled into view. Top edge of the scroll container.</para>
        /// </summary>
        TopEdge = 2,
        /// <summary>
        /// <para>A preferred position for the node scrolled into view. Bottom edge of the scroll container.</para>
        /// </summary>
        BottomEdge = 3,
        /// <summary>
        /// <para>A preferred position for the node scrolled into view. Left edge of the scroll container.</para>
        /// </summary>
        LeftEdge = 4,
        /// <summary>
        /// <para>A preferred position for the node scrolled into view. Right edge of the scroll container.</para>
        /// </summary>
        RightEdge = 5
    }

    private static readonly StringName NativeName = "AccessibilityServer";

    private static AccessibilityServerInstance singleton;

    public static AccessibilityServerInstance Singleton =>
        singleton ??= (AccessibilityServerInstance)InteropUtils.EngineGetSingleton("AccessibilityServer");

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.IsSupported, 36873697ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if screen reader is support by this implementation.</para>
    /// </summary>
    public static bool IsSupported()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind0, GodotObject.GetPtr(Singleton)).ToBool();
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.CreateElement, 3846965249ul);

    /// <summary>
    /// <para>Creates a new, empty accessibility element resource.</para>
    /// <para><b>Note:</b> An accessibility element is created and freed automatically for each <see cref="Godot.Node"/>. In general, this function should not be called manually.</para>
    /// </summary>
    public static Rid CreateElement(int windowId, AccessibilityServer.AccessibilityRole role)
    {
        Rid ret = NativeCalls.godot_icall_2_59(MethodBind1, GodotObject.GetPtr(Singleton), windowId, (int)role);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.CreateSubElement, 1151690429ul);

    /// <summary>
    /// <para>Creates a new, empty accessibility sub-element resource. Sub-elements can be used to provide accessibility information for objects which are not <see cref="Godot.Node"/>s, such as list items, table cells, or menu items. Sub-elements are freed automatically when the parent element is freed, or can be freed early using the <see cref="Godot.AccessibilityServer.FreeElement(Rid)"/> method.</para>
    /// </summary>
    public static Rid CreateSubElement(Rid parentRid, AccessibilityServer.AccessibilityRole role, int insertPos = -1)
    {
        Rid ret = NativeCalls.godot_icall_3_60(MethodBind2, GodotObject.GetPtr(Singleton), parentRid, (int)role, insertPos);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.CreateSubTextEditElements, 2702009895ul);

    /// <summary>
    /// <para>Creates a new, empty accessibility sub-element from the shaped text buffer. Sub-elements are freed automatically when the parent element is freed, or can be freed early using the <see cref="Godot.AccessibilityServer.FreeElement(Rid)"/> method.</para>
    /// <para>If <paramref name="isLastLine"/> is <see langword="true"/>, no trailing newline is appended to the text content. Set to <see langword="true"/> for the last line in multi-line text fields and for single-line text fields.</para>
    /// </summary>
    public static Rid CreateSubTextEditElements(Rid parentRid, Rid shapedText, float minHeight, int insertPos = -1, bool isLastLine = false)
    {
        Rid ret = NativeCalls.godot_icall_5_61(MethodBind3, GodotObject.GetPtr(Singleton), parentRid, shapedText, minHeight, insertPos, isLastLine.ToGodotBool());
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.HasElement, 4155700596ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if <paramref name="id"/> is a valid accessibility element.</para>
    /// </summary>
    public static bool HasElement(Rid id)
    {
        bool ret = NativeCalls.godot_icall_1_62(MethodBind4, GodotObject.GetPtr(Singleton), id).ToBool();
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.FreeElement, 2722037293ul);

    /// <summary>
    /// <para>Frees the accessibility element <paramref name="id"/> created by <see cref="Godot.AccessibilityServer.CreateElement(int, AccessibilityServer.AccessibilityRole)"/>, <see cref="Godot.AccessibilityServer.CreateSubElement(Rid, AccessibilityServer.AccessibilityRole, int)"/>, or <see cref="Godot.AccessibilityServer.CreateSubTextEditElements(Rid, Rid, float, int, bool)"/>.</para>
    /// </summary>
    public static void FreeElement(Rid id)
    {
        NativeCalls.godot_icall_1_63(MethodBind5, GodotObject.GetPtr(Singleton), id);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.ElementSetMeta, 3175752987ul);

    /// <summary>
    /// <para>Sets the metadata of the accessibility element <paramref name="id"/> to <paramref name="meta"/>.</para>
    /// </summary>
    public static void ElementSetMeta(Rid id, Variant meta)
    {
        NativeCalls.godot_icall_2_64(MethodBind6, GodotObject.GetPtr(Singleton), id, meta);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.ElementGetMeta, 4171304767ul);

    /// <summary>
    /// <para>Returns the metadata of the accessibility element <paramref name="id"/>.</para>
    /// </summary>
    public static Variant ElementGetMeta(Rid id)
    {
        Variant ret = NativeCalls.godot_icall_1_65(MethodBind7, GodotObject.GetPtr(Singleton), id);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.SetWindowRect, 2386961724ul);

    /// <summary>
    /// <para>Sets window outer (with decorations) and inner (without decorations) bounds for assistive apps.</para>
    /// <para><b>Note:</b> This method is implemented on Linux, macOS, and Windows.</para>
    /// <para><b>Note:</b> Advanced users only! <see cref="Godot.Window"/> objects call this method automatically.</para>
    /// </summary>
    public static unsafe void SetWindowRect(int windowId, Rect2 rectOut, Rect2 rectIn)
    {
        NativeCalls.godot_icall_3_66(MethodBind8, GodotObject.GetPtr(Singleton), windowId, &rectOut, &rectIn);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind9 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.SetWindowFocused, 300928843ul);

    /// <summary>
    /// <para>Sets the window focused state for assistive apps.</para>
    /// <para><b>Note:</b> This method is implemented on Linux, macOS, and Windows.</para>
    /// <para><b>Note:</b> Advanced users only! <see cref="Godot.Window"/> objects call this method automatically.</para>
    /// </summary>
    public static void SetWindowFocused(int windowId, bool focused)
    {
        NativeCalls.godot_icall_2_67(MethodBind9, GodotObject.GetPtr(Singleton), windowId, focused.ToGodotBool());
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind10 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetFocus, 2722037293ul);

    /// <summary>
    /// <para>Sets currently focused element.</para>
    /// </summary>
    public static void UpdateSetFocus(Rid id)
    {
        NativeCalls.godot_icall_1_63(MethodBind10, GodotObject.GetPtr(Singleton), id);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind11 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.GetWindowRoot, 495598643ul);

    /// <summary>
    /// <para>Returns the main accessibility element of the OS native window.</para>
    /// </summary>
    public static Rid GetWindowRoot(int windowId)
    {
        Rid ret = NativeCalls.godot_icall_1_68(MethodBind11, GodotObject.GetPtr(Singleton), windowId);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind12 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetRole, 3747886520ul);

    /// <summary>
    /// <para>Sets element accessibility role.</para>
    /// </summary>
    public static void UpdateSetRole(Rid id, AccessibilityServer.AccessibilityRole role)
    {
        NativeCalls.godot_icall_2_69(MethodBind12, GodotObject.GetPtr(Singleton), id, (int)role);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind13 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetName, 2726140452ul);

    /// <summary>
    /// <para>Sets element accessibility name.</para>
    /// </summary>
    public static void UpdateSetName(Rid id, string name)
    {
        NativeCalls.godot_icall_2_70(MethodBind13, GodotObject.GetPtr(Singleton), id, name);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind14 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetBrailleLabel, 2726140452ul);

    /// <summary>
    /// <para>Sets element accessibility label for Braille display.</para>
    /// </summary>
    public static void UpdateSetBrailleLabel(Rid id, string name)
    {
        NativeCalls.godot_icall_2_70(MethodBind14, GodotObject.GetPtr(Singleton), id, name);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind15 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetBrailleRoleDescription, 2726140452ul);

    /// <summary>
    /// <para>Sets element accessibility role description for Braille display.</para>
    /// </summary>
    public static void UpdateSetBrailleRoleDescription(Rid id, string description)
    {
        NativeCalls.godot_icall_2_70(MethodBind15, GodotObject.GetPtr(Singleton), id, description);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind16 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetExtraInfo, 2726140452ul);

    /// <summary>
    /// <para>Sets element accessibility extra information added to the element name.</para>
    /// </summary>
    public static void UpdateSetExtraInfo(Rid id, string name)
    {
        NativeCalls.godot_icall_2_70(MethodBind16, GodotObject.GetPtr(Singleton), id, name);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind17 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetDescription, 2726140452ul);

    /// <summary>
    /// <para>Sets element accessibility description.</para>
    /// </summary>
    public static void UpdateSetDescription(Rid id, string description)
    {
        NativeCalls.godot_icall_2_70(MethodBind17, GodotObject.GetPtr(Singleton), id, description);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind18 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetValue, 2726140452ul);

    /// <summary>
    /// <para>Sets element text value.</para>
    /// </summary>
    public static void UpdateSetValue(Rid id, string value)
    {
        NativeCalls.godot_icall_2_70(MethodBind18, GodotObject.GetPtr(Singleton), id, value);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind19 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetTooltip, 2726140452ul);

    /// <summary>
    /// <para>Sets tooltip text.</para>
    /// </summary>
    public static void UpdateSetTooltip(Rid id, string tooltip)
    {
        NativeCalls.godot_icall_2_70(MethodBind19, GodotObject.GetPtr(Singleton), id, tooltip);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind20 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetBounds, 1378122625ul);

    /// <summary>
    /// <para>Sets element bounding box, relative to the node position.</para>
    /// </summary>
    public static unsafe void UpdateSetBounds(Rid id, Rect2 rect)
    {
        NativeCalls.godot_icall_2_71(MethodBind20, GodotObject.GetPtr(Singleton), id, &rect);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind21 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetTransform, 1246044741ul);

    /// <summary>
    /// <para>Sets element 2D transform.</para>
    /// </summary>
    public static unsafe void UpdateSetTransform(Rid id, Transform2D transform)
    {
        NativeCalls.godot_icall_2_72(MethodBind21, GodotObject.GetPtr(Singleton), id, &transform);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind22 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateAddChild, 395945892ul);

    /// <summary>
    /// <para>Adds a child accessibility element.</para>
    /// <para><b>Note:</b> <see cref="Godot.Node"/> children and sub-elements are added to the child list automatically.</para>
    /// </summary>
    public static void UpdateAddChild(Rid id, Rid childId)
    {
        NativeCalls.godot_icall_2_73(MethodBind22, GodotObject.GetPtr(Singleton), id, childId);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind23 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateAddRelatedControls, 395945892ul);

    /// <summary>
    /// <para>Adds an element that is controlled by this element.</para>
    /// </summary>
    public static void UpdateAddRelatedControls(Rid id, Rid relatedId)
    {
        NativeCalls.godot_icall_2_73(MethodBind23, GodotObject.GetPtr(Singleton), id, relatedId);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind24 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateAddRelatedDetails, 395945892ul);

    /// <summary>
    /// <para>Adds an element that details this element.</para>
    /// </summary>
    public static void UpdateAddRelatedDetails(Rid id, Rid relatedId)
    {
        NativeCalls.godot_icall_2_73(MethodBind24, GodotObject.GetPtr(Singleton), id, relatedId);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind25 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateAddRelatedDescribedBy, 395945892ul);

    /// <summary>
    /// <para>Adds an element that describes this element.</para>
    /// </summary>
    public static void UpdateAddRelatedDescribedBy(Rid id, Rid relatedId)
    {
        NativeCalls.godot_icall_2_73(MethodBind25, GodotObject.GetPtr(Singleton), id, relatedId);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind26 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateAddRelatedFlowTo, 395945892ul);

    /// <summary>
    /// <para>Adds an element that this element flow into.</para>
    /// </summary>
    public static void UpdateAddRelatedFlowTo(Rid id, Rid relatedId)
    {
        NativeCalls.godot_icall_2_73(MethodBind26, GodotObject.GetPtr(Singleton), id, relatedId);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind27 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateAddRelatedLabeledBy, 395945892ul);

    /// <summary>
    /// <para>Adds an element that labels this element.</para>
    /// </summary>
    public static void UpdateAddRelatedLabeledBy(Rid id, Rid relatedId)
    {
        NativeCalls.godot_icall_2_73(MethodBind27, GodotObject.GetPtr(Singleton), id, relatedId);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind28 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateAddRelatedRadioGroup, 395945892ul);

    /// <summary>
    /// <para>Adds an element that is part of the same radio group.</para>
    /// <para><b>Note:</b> This method should be called on each element of the group, using all other elements as <paramref name="relatedId"/>.</para>
    /// </summary>
    public static void UpdateAddRelatedRadioGroup(Rid id, Rid relatedId)
    {
        NativeCalls.godot_icall_2_73(MethodBind28, GodotObject.GetPtr(Singleton), id, relatedId);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind29 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetActiveDescendant, 395945892ul);

    /// <summary>
    /// <para>Adds an element that is an active descendant of this element.</para>
    /// </summary>
    public static void UpdateSetActiveDescendant(Rid id, Rid otherId)
    {
        NativeCalls.godot_icall_2_73(MethodBind29, GodotObject.GetPtr(Singleton), id, otherId);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind30 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetNextOnLine, 395945892ul);

    /// <summary>
    /// <para>Sets next element on the line.</para>
    /// </summary>
    public static void UpdateSetNextOnLine(Rid id, Rid otherId)
    {
        NativeCalls.godot_icall_2_73(MethodBind30, GodotObject.GetPtr(Singleton), id, otherId);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind31 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetPreviousOnLine, 395945892ul);

    /// <summary>
    /// <para>Sets previous element on the line.</para>
    /// </summary>
    public static void UpdateSetPreviousOnLine(Rid id, Rid otherId)
    {
        NativeCalls.godot_icall_2_73(MethodBind31, GodotObject.GetPtr(Singleton), id, otherId);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind32 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetMemberOf, 395945892ul);

    /// <summary>
    /// <para>Sets the element to be a member of the group.</para>
    /// </summary>
    public static void UpdateSetMemberOf(Rid id, Rid groupId)
    {
        NativeCalls.godot_icall_2_73(MethodBind32, GodotObject.GetPtr(Singleton), id, groupId);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind33 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetInPageLinkTarget, 395945892ul);

    /// <summary>
    /// <para>Sets target element for the link.</para>
    /// </summary>
    public static void UpdateSetInPageLinkTarget(Rid id, Rid otherId)
    {
        NativeCalls.godot_icall_2_73(MethodBind33, GodotObject.GetPtr(Singleton), id, otherId);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind34 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetErrorMessage, 395945892ul);

    /// <summary>
    /// <para>Sets an element which contains an error message for this element.</para>
    /// </summary>
    public static void UpdateSetErrorMessage(Rid id, Rid otherId)
    {
        NativeCalls.godot_icall_2_73(MethodBind34, GodotObject.GetPtr(Singleton), id, otherId);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind35 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetLive, 2993365237ul);

    /// <summary>
    /// <para>Sets the priority of the live region updates.</para>
    /// </summary>
    public static void UpdateSetLive(Rid id, AccessibilityServer.AccessibilityLiveMode live)
    {
        NativeCalls.godot_icall_2_69(MethodBind35, GodotObject.GetPtr(Singleton), id, (int)live);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind36 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateAddAction, 3960092835ul);

    /// <summary>
    /// <para>Adds a callback for the accessibility action (action which can be performed by using a special screen reader command or buttons on the Braille display), and marks this action as supported. The action callback receives one <see cref="Godot.Variant"/> argument, which value depends on action type.</para>
    /// </summary>
    public static void UpdateAddAction(Rid id, AccessibilityServer.AccessibilityAction action, Callable callable)
    {
        NativeCalls.godot_icall_3_74(MethodBind36, GodotObject.GetPtr(Singleton), id, (int)action, callable);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind37 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateAddCustomAction, 4153150897ul);

    /// <summary>
    /// <para>Adds support for a custom accessibility action. <paramref name="actionId"/> is passed as an argument to the callback of <see cref="Godot.AccessibilityServer.AccessibilityAction.Custom"/> action.</para>
    /// </summary>
    public static void UpdateAddCustomAction(Rid id, int actionId, string actionDescription)
    {
        NativeCalls.godot_icall_3_75(MethodBind37, GodotObject.GetPtr(Singleton), id, actionId, actionDescription);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind38 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetTableRowCount, 3411492887ul);

    /// <summary>
    /// <para>Sets number of rows in the table.</para>
    /// </summary>
    public static void UpdateSetTableRowCount(Rid id, int count)
    {
        NativeCalls.godot_icall_2_69(MethodBind38, GodotObject.GetPtr(Singleton), id, count);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind39 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetTableColumnCount, 3411492887ul);

    /// <summary>
    /// <para>Sets number of columns in the table.</para>
    /// </summary>
    public static void UpdateSetTableColumnCount(Rid id, int count)
    {
        NativeCalls.godot_icall_2_69(MethodBind39, GodotObject.GetPtr(Singleton), id, count);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind40 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetTableRowIndex, 3411492887ul);

    /// <summary>
    /// <para>Sets position of the row in the table.</para>
    /// </summary>
    public static void UpdateSetTableRowIndex(Rid id, int index)
    {
        NativeCalls.godot_icall_2_69(MethodBind40, GodotObject.GetPtr(Singleton), id, index);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind41 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetTableColumnIndex, 3411492887ul);

    /// <summary>
    /// <para>Sets position of the column.</para>
    /// </summary>
    public static void UpdateSetTableColumnIndex(Rid id, int index)
    {
        NativeCalls.godot_icall_2_69(MethodBind41, GodotObject.GetPtr(Singleton), id, index);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind42 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetTableCellPosition, 4288446313ul);

    /// <summary>
    /// <para>Sets cell position in the table.</para>
    /// </summary>
    public static void UpdateSetTableCellPosition(Rid id, int rowIndex, int columnIndex)
    {
        NativeCalls.godot_icall_3_76(MethodBind42, GodotObject.GetPtr(Singleton), id, rowIndex, columnIndex);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind43 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetTableCellSpan, 4288446313ul);

    /// <summary>
    /// <para>Sets cell row/column span.</para>
    /// </summary>
    public static void UpdateSetTableCellSpan(Rid id, int rowSpan, int columnSpan)
    {
        NativeCalls.godot_icall_3_76(MethodBind43, GodotObject.GetPtr(Singleton), id, rowSpan, columnSpan);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind44 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetListItemCount, 3411492887ul);

    /// <summary>
    /// <para>Sets number of items in the list.</para>
    /// </summary>
    public static void UpdateSetListItemCount(Rid id, int size)
    {
        NativeCalls.godot_icall_2_69(MethodBind44, GodotObject.GetPtr(Singleton), id, size);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind45 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetListItemIndex, 3411492887ul);

    /// <summary>
    /// <para>Sets the position of the element in the list.</para>
    /// </summary>
    public static void UpdateSetListItemIndex(Rid id, int index)
    {
        NativeCalls.godot_icall_2_69(MethodBind45, GodotObject.GetPtr(Singleton), id, index);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind46 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetListItemLevel, 3411492887ul);

    /// <summary>
    /// <para>Sets the hierarchical level of the element in the list.</para>
    /// </summary>
    public static void UpdateSetListItemLevel(Rid id, int level)
    {
        NativeCalls.godot_icall_2_69(MethodBind46, GodotObject.GetPtr(Singleton), id, level);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind47 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetListItemSelected, 1265174801ul);

    /// <summary>
    /// <para>Sets list/tree item selected status.</para>
    /// </summary>
    public static void UpdateSetListItemSelected(Rid id, bool selected)
    {
        NativeCalls.godot_icall_2_77(MethodBind47, GodotObject.GetPtr(Singleton), id, selected.ToGodotBool());
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind48 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetListItemExpanded, 1265174801ul);

    /// <summary>
    /// <para>Sets list/tree item expanded status.</para>
    /// </summary>
    public static void UpdateSetListItemExpanded(Rid id, bool expanded)
    {
        NativeCalls.godot_icall_2_77(MethodBind48, GodotObject.GetPtr(Singleton), id, expanded.ToGodotBool());
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind49 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetPopupType, 690307634ul);

    /// <summary>
    /// <para>Sets popup type for popup buttons.</para>
    /// </summary>
    public static void UpdateSetPopupType(Rid id, AccessibilityServer.AccessibilityPopupType popup)
    {
        NativeCalls.godot_icall_2_69(MethodBind49, GodotObject.GetPtr(Singleton), id, (int)popup);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind50 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetChecked, 1265174801ul);

    /// <summary>
    /// <para>Sets element checked state.</para>
    /// </summary>
    public static void UpdateSetChecked(Rid id, bool checekd)
    {
        NativeCalls.godot_icall_2_77(MethodBind50, GodotObject.GetPtr(Singleton), id, checekd.ToGodotBool());
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind51 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetNumValue, 1794382983ul);

    /// <summary>
    /// <para>Sets numeric value.</para>
    /// </summary>
    public static void UpdateSetNumValue(Rid id, double position)
    {
        NativeCalls.godot_icall_2_78(MethodBind51, GodotObject.GetPtr(Singleton), id, position);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind52 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetNumRange, 2513314492ul);

    /// <summary>
    /// <para>Sets numeric value range.</para>
    /// </summary>
    public static void UpdateSetNumRange(Rid id, double min, double max)
    {
        NativeCalls.godot_icall_3_79(MethodBind52, GodotObject.GetPtr(Singleton), id, min, max);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind53 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetNumStep, 1794382983ul);

    /// <summary>
    /// <para>Sets numeric value step.</para>
    /// </summary>
    public static void UpdateSetNumStep(Rid id, double step)
    {
        NativeCalls.godot_icall_2_78(MethodBind53, GodotObject.GetPtr(Singleton), id, step);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind54 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetNumJump, 1794382983ul);

    /// <summary>
    /// <para>Sets numeric value jump.</para>
    /// </summary>
    public static void UpdateSetNumJump(Rid id, double jump)
    {
        NativeCalls.godot_icall_2_78(MethodBind54, GodotObject.GetPtr(Singleton), id, jump);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind55 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetScrollX, 1794382983ul);

    /// <summary>
    /// <para>Sets scroll bar x position.</para>
    /// </summary>
    public static void UpdateSetScrollX(Rid id, double position)
    {
        NativeCalls.godot_icall_2_78(MethodBind55, GodotObject.GetPtr(Singleton), id, position);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind56 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetScrollXRange, 2513314492ul);

    /// <summary>
    /// <para>Sets scroll bar x range.</para>
    /// </summary>
    public static void UpdateSetScrollXRange(Rid id, double min, double max)
    {
        NativeCalls.godot_icall_3_79(MethodBind56, GodotObject.GetPtr(Singleton), id, min, max);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind57 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetScrollY, 1794382983ul);

    /// <summary>
    /// <para>Sets scroll bar y position.</para>
    /// </summary>
    public static void UpdateSetScrollY(Rid id, double position)
    {
        NativeCalls.godot_icall_2_78(MethodBind57, GodotObject.GetPtr(Singleton), id, position);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind58 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetScrollYRange, 2513314492ul);

    /// <summary>
    /// <para>Sets scroll bar y range.</para>
    /// </summary>
    public static void UpdateSetScrollYRange(Rid id, double min, double max)
    {
        NativeCalls.godot_icall_3_79(MethodBind58, GodotObject.GetPtr(Singleton), id, min, max);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind59 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetTextDecorations, 457503484ul);

    /// <summary>
    /// <para>Sets text underline/overline/strikethrough.</para>
    /// </summary>
    /// <param name="color">If the parameter is null, then the default value is <c>new Color(0.0f, 0.0f, 0.0f, 1.0f)</c>.</param>
    public static unsafe void UpdateSetTextDecorations(Rid id, bool underline, bool strikethrough, bool overline, Nullable<Color> color = null)
    {
        Color colorOrDefVal = color.HasValue ? color.Value : new Color(0.0f, 0.0f, 0.0f, 1.0f);
        NativeCalls.godot_icall_5_80(MethodBind59, GodotObject.GetPtr(Singleton), id, underline.ToGodotBool(), strikethrough.ToGodotBool(), overline.ToGodotBool(), &colorOrDefVal);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind60 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetTextAlign, 3725995085ul);

    /// <summary>
    /// <para>Sets element text alignment.</para>
    /// </summary>
    public static void UpdateSetTextAlign(Rid id, HorizontalAlignment align)
    {
        NativeCalls.godot_icall_2_69(MethodBind60, GodotObject.GetPtr(Singleton), id, (int)align);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind61 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetTextSelection, 3119144029ul);

    /// <summary>
    /// <para>Sets text selection to the text field. <paramref name="textStartId"/> and <paramref name="textEndId"/> should be elements created by <see cref="Godot.AccessibilityServer.CreateSubTextEditElements(Rid, Rid, float, int, bool)"/>. Character offsets are relative to the corresponding element.</para>
    /// </summary>
    public static void UpdateSetTextSelection(Rid id, Rid textStartId, int startChar, Rid textEndId, int endChar)
    {
        NativeCalls.godot_icall_5_81(MethodBind61, GodotObject.GetPtr(Singleton), id, textStartId, startChar, textEndId, endChar);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind62 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetFlag, 1473043386ul);

    /// <summary>
    /// <para>Sets element flag.</para>
    /// </summary>
    public static void UpdateSetFlag(Rid id, AccessibilityServer.AccessibilityFlags flag, bool value)
    {
        NativeCalls.godot_icall_3_82(MethodBind62, GodotObject.GetPtr(Singleton), id, (int)flag, value.ToGodotBool());
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind63 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetClassname, 2726140452ul);

    /// <summary>
    /// <para>Sets element class name.</para>
    /// </summary>
    public static void UpdateSetClassname(Rid id, string classname)
    {
        NativeCalls.godot_icall_2_70(MethodBind63, GodotObject.GetPtr(Singleton), id, classname);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind64 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetPlaceholder, 2726140452ul);

    /// <summary>
    /// <para>Sets placeholder text.</para>
    /// </summary>
    public static void UpdateSetPlaceholder(Rid id, string placeholder)
    {
        NativeCalls.godot_icall_2_70(MethodBind64, GodotObject.GetPtr(Singleton), id, placeholder);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind65 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetLanguage, 2726140452ul);

    /// <summary>
    /// <para>Sets element text language.</para>
    /// </summary>
    public static void UpdateSetLanguage(Rid id, string language)
    {
        NativeCalls.godot_icall_2_70(MethodBind65, GodotObject.GetPtr(Singleton), id, language);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind66 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetTextOrientation, 1265174801ul);

    /// <summary>
    /// <para>Sets text orientation.</para>
    /// </summary>
    public static void UpdateSetTextOrientation(Rid id, bool vertical)
    {
        NativeCalls.godot_icall_2_77(MethodBind66, GodotObject.GetPtr(Singleton), id, vertical.ToGodotBool());
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind67 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetListOrientation, 1265174801ul);

    /// <summary>
    /// <para>Sets the orientation of the list elements.</para>
    /// </summary>
    public static void UpdateSetListOrientation(Rid id, bool vertical)
    {
        NativeCalls.godot_icall_2_77(MethodBind67, GodotObject.GetPtr(Singleton), id, vertical.ToGodotBool());
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind68 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetShortcut, 2726140452ul);

    /// <summary>
    /// <para>Sets the list of keyboard shortcuts used by element.</para>
    /// </summary>
    public static void UpdateSetShortcut(Rid id, string shortcut)
    {
        NativeCalls.godot_icall_2_70(MethodBind68, GodotObject.GetPtr(Singleton), id, shortcut);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind69 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetUrl, 2726140452ul);

    /// <summary>
    /// <para>Sets link URL.</para>
    /// </summary>
    public static void UpdateSetUrl(Rid id, string url)
    {
        NativeCalls.godot_icall_2_70(MethodBind69, GodotObject.GetPtr(Singleton), id, url);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind70 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetRoleDescription, 2726140452ul);

    /// <summary>
    /// <para>Sets element accessibility role description text.</para>
    /// </summary>
    public static void UpdateSetRoleDescription(Rid id, string description)
    {
        NativeCalls.godot_icall_2_70(MethodBind70, GodotObject.GetPtr(Singleton), id, description);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind71 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetStateDescription, 2726140452ul);

    /// <summary>
    /// <para>Sets human-readable description of the current checked state.</para>
    /// </summary>
    public static void UpdateSetStateDescription(Rid id, string description)
    {
        NativeCalls.godot_icall_2_70(MethodBind71, GodotObject.GetPtr(Singleton), id, description);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind72 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetColorValue, 2948539648ul);

    /// <summary>
    /// <para>Sets element color value.</para>
    /// </summary>
    public static unsafe void UpdateSetColorValue(Rid id, Color color)
    {
        NativeCalls.godot_icall_2_83(MethodBind72, GodotObject.GetPtr(Singleton), id, &color);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind73 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetBackgroundColor, 2948539648ul);

    /// <summary>
    /// <para>Sets element background color.</para>
    /// </summary>
    public static unsafe void UpdateSetBackgroundColor(Rid id, Color color)
    {
        NativeCalls.godot_icall_2_83(MethodBind73, GodotObject.GetPtr(Singleton), id, &color);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind74 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.UpdateSetForegroundColor, 2948539648ul);

    /// <summary>
    /// <para>Sets element foreground color.</para>
    /// </summary>
    public static unsafe void UpdateSetForegroundColor(Rid id, Color color)
    {
        NativeCalls.godot_icall_2_83(MethodBind74, GodotObject.GetPtr(Singleton), id, &color);
    }

    /// <summary>
    /// Cached StringNames for the properties and fields contained in this class, for fast lookup.
    /// </summary>
    public class PropertyName
    {
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public class MethodName
    {
        /// <summary>
        /// Cached name for the 'is_supported' method.
        /// </summary>
        public static readonly StringName IsSupported = "is_supported";
        /// <summary>
        /// Cached name for the 'create_element' method.
        /// </summary>
        public static readonly StringName CreateElement = "create_element";
        /// <summary>
        /// Cached name for the 'create_sub_element' method.
        /// </summary>
        public static readonly StringName CreateSubElement = "create_sub_element";
        /// <summary>
        /// Cached name for the 'create_sub_text_edit_elements' method.
        /// </summary>
        public static readonly StringName CreateSubTextEditElements = "create_sub_text_edit_elements";
        /// <summary>
        /// Cached name for the 'has_element' method.
        /// </summary>
        public static readonly StringName HasElement = "has_element";
        /// <summary>
        /// Cached name for the 'free_element' method.
        /// </summary>
        public static readonly StringName FreeElement = "free_element";
        /// <summary>
        /// Cached name for the 'element_set_meta' method.
        /// </summary>
        public static readonly StringName ElementSetMeta = "element_set_meta";
        /// <summary>
        /// Cached name for the 'element_get_meta' method.
        /// </summary>
        public static readonly StringName ElementGetMeta = "element_get_meta";
        /// <summary>
        /// Cached name for the 'set_window_rect' method.
        /// </summary>
        public static readonly StringName SetWindowRect = "set_window_rect";
        /// <summary>
        /// Cached name for the 'set_window_focused' method.
        /// </summary>
        public static readonly StringName SetWindowFocused = "set_window_focused";
        /// <summary>
        /// Cached name for the 'update_set_focus' method.
        /// </summary>
        public static readonly StringName UpdateSetFocus = "update_set_focus";
        /// <summary>
        /// Cached name for the 'get_window_root' method.
        /// </summary>
        public static readonly StringName GetWindowRoot = "get_window_root";
        /// <summary>
        /// Cached name for the 'update_set_role' method.
        /// </summary>
        public static readonly StringName UpdateSetRole = "update_set_role";
        /// <summary>
        /// Cached name for the 'update_set_name' method.
        /// </summary>
        public static readonly StringName UpdateSetName = "update_set_name";
        /// <summary>
        /// Cached name for the 'update_set_braille_label' method.
        /// </summary>
        public static readonly StringName UpdateSetBrailleLabel = "update_set_braille_label";
        /// <summary>
        /// Cached name for the 'update_set_braille_role_description' method.
        /// </summary>
        public static readonly StringName UpdateSetBrailleRoleDescription = "update_set_braille_role_description";
        /// <summary>
        /// Cached name for the 'update_set_extra_info' method.
        /// </summary>
        public static readonly StringName UpdateSetExtraInfo = "update_set_extra_info";
        /// <summary>
        /// Cached name for the 'update_set_description' method.
        /// </summary>
        public static readonly StringName UpdateSetDescription = "update_set_description";
        /// <summary>
        /// Cached name for the 'update_set_value' method.
        /// </summary>
        public static readonly StringName UpdateSetValue = "update_set_value";
        /// <summary>
        /// Cached name for the 'update_set_tooltip' method.
        /// </summary>
        public static readonly StringName UpdateSetTooltip = "update_set_tooltip";
        /// <summary>
        /// Cached name for the 'update_set_bounds' method.
        /// </summary>
        public static readonly StringName UpdateSetBounds = "update_set_bounds";
        /// <summary>
        /// Cached name for the 'update_set_transform' method.
        /// </summary>
        public static readonly StringName UpdateSetTransform = "update_set_transform";
        /// <summary>
        /// Cached name for the 'update_add_child' method.
        /// </summary>
        public static readonly StringName UpdateAddChild = "update_add_child";
        /// <summary>
        /// Cached name for the 'update_add_related_controls' method.
        /// </summary>
        public static readonly StringName UpdateAddRelatedControls = "update_add_related_controls";
        /// <summary>
        /// Cached name for the 'update_add_related_details' method.
        /// </summary>
        public static readonly StringName UpdateAddRelatedDetails = "update_add_related_details";
        /// <summary>
        /// Cached name for the 'update_add_related_described_by' method.
        /// </summary>
        public static readonly StringName UpdateAddRelatedDescribedBy = "update_add_related_described_by";
        /// <summary>
        /// Cached name for the 'update_add_related_flow_to' method.
        /// </summary>
        public static readonly StringName UpdateAddRelatedFlowTo = "update_add_related_flow_to";
        /// <summary>
        /// Cached name for the 'update_add_related_labeled_by' method.
        /// </summary>
        public static readonly StringName UpdateAddRelatedLabeledBy = "update_add_related_labeled_by";
        /// <summary>
        /// Cached name for the 'update_add_related_radio_group' method.
        /// </summary>
        public static readonly StringName UpdateAddRelatedRadioGroup = "update_add_related_radio_group";
        /// <summary>
        /// Cached name for the 'update_set_active_descendant' method.
        /// </summary>
        public static readonly StringName UpdateSetActiveDescendant = "update_set_active_descendant";
        /// <summary>
        /// Cached name for the 'update_set_next_on_line' method.
        /// </summary>
        public static readonly StringName UpdateSetNextOnLine = "update_set_next_on_line";
        /// <summary>
        /// Cached name for the 'update_set_previous_on_line' method.
        /// </summary>
        public static readonly StringName UpdateSetPreviousOnLine = "update_set_previous_on_line";
        /// <summary>
        /// Cached name for the 'update_set_member_of' method.
        /// </summary>
        public static readonly StringName UpdateSetMemberOf = "update_set_member_of";
        /// <summary>
        /// Cached name for the 'update_set_in_page_link_target' method.
        /// </summary>
        public static readonly StringName UpdateSetInPageLinkTarget = "update_set_in_page_link_target";
        /// <summary>
        /// Cached name for the 'update_set_error_message' method.
        /// </summary>
        public static readonly StringName UpdateSetErrorMessage = "update_set_error_message";
        /// <summary>
        /// Cached name for the 'update_set_live' method.
        /// </summary>
        public static readonly StringName UpdateSetLive = "update_set_live";
        /// <summary>
        /// Cached name for the 'update_add_action' method.
        /// </summary>
        public static readonly StringName UpdateAddAction = "update_add_action";
        /// <summary>
        /// Cached name for the 'update_add_custom_action' method.
        /// </summary>
        public static readonly StringName UpdateAddCustomAction = "update_add_custom_action";
        /// <summary>
        /// Cached name for the 'update_set_table_row_count' method.
        /// </summary>
        public static readonly StringName UpdateSetTableRowCount = "update_set_table_row_count";
        /// <summary>
        /// Cached name for the 'update_set_table_column_count' method.
        /// </summary>
        public static readonly StringName UpdateSetTableColumnCount = "update_set_table_column_count";
        /// <summary>
        /// Cached name for the 'update_set_table_row_index' method.
        /// </summary>
        public static readonly StringName UpdateSetTableRowIndex = "update_set_table_row_index";
        /// <summary>
        /// Cached name for the 'update_set_table_column_index' method.
        /// </summary>
        public static readonly StringName UpdateSetTableColumnIndex = "update_set_table_column_index";
        /// <summary>
        /// Cached name for the 'update_set_table_cell_position' method.
        /// </summary>
        public static readonly StringName UpdateSetTableCellPosition = "update_set_table_cell_position";
        /// <summary>
        /// Cached name for the 'update_set_table_cell_span' method.
        /// </summary>
        public static readonly StringName UpdateSetTableCellSpan = "update_set_table_cell_span";
        /// <summary>
        /// Cached name for the 'update_set_list_item_count' method.
        /// </summary>
        public static readonly StringName UpdateSetListItemCount = "update_set_list_item_count";
        /// <summary>
        /// Cached name for the 'update_set_list_item_index' method.
        /// </summary>
        public static readonly StringName UpdateSetListItemIndex = "update_set_list_item_index";
        /// <summary>
        /// Cached name for the 'update_set_list_item_level' method.
        /// </summary>
        public static readonly StringName UpdateSetListItemLevel = "update_set_list_item_level";
        /// <summary>
        /// Cached name for the 'update_set_list_item_selected' method.
        /// </summary>
        public static readonly StringName UpdateSetListItemSelected = "update_set_list_item_selected";
        /// <summary>
        /// Cached name for the 'update_set_list_item_expanded' method.
        /// </summary>
        public static readonly StringName UpdateSetListItemExpanded = "update_set_list_item_expanded";
        /// <summary>
        /// Cached name for the 'update_set_popup_type' method.
        /// </summary>
        public static readonly StringName UpdateSetPopupType = "update_set_popup_type";
        /// <summary>
        /// Cached name for the 'update_set_checked' method.
        /// </summary>
        public static readonly StringName UpdateSetChecked = "update_set_checked";
        /// <summary>
        /// Cached name for the 'update_set_num_value' method.
        /// </summary>
        public static readonly StringName UpdateSetNumValue = "update_set_num_value";
        /// <summary>
        /// Cached name for the 'update_set_num_range' method.
        /// </summary>
        public static readonly StringName UpdateSetNumRange = "update_set_num_range";
        /// <summary>
        /// Cached name for the 'update_set_num_step' method.
        /// </summary>
        public static readonly StringName UpdateSetNumStep = "update_set_num_step";
        /// <summary>
        /// Cached name for the 'update_set_num_jump' method.
        /// </summary>
        public static readonly StringName UpdateSetNumJump = "update_set_num_jump";
        /// <summary>
        /// Cached name for the 'update_set_scroll_x' method.
        /// </summary>
        public static readonly StringName UpdateSetScrollX = "update_set_scroll_x";
        /// <summary>
        /// Cached name for the 'update_set_scroll_x_range' method.
        /// </summary>
        public static readonly StringName UpdateSetScrollXRange = "update_set_scroll_x_range";
        /// <summary>
        /// Cached name for the 'update_set_scroll_y' method.
        /// </summary>
        public static readonly StringName UpdateSetScrollY = "update_set_scroll_y";
        /// <summary>
        /// Cached name for the 'update_set_scroll_y_range' method.
        /// </summary>
        public static readonly StringName UpdateSetScrollYRange = "update_set_scroll_y_range";
        /// <summary>
        /// Cached name for the 'update_set_text_decorations' method.
        /// </summary>
        public static readonly StringName UpdateSetTextDecorations = "update_set_text_decorations";
        /// <summary>
        /// Cached name for the 'update_set_text_align' method.
        /// </summary>
        public static readonly StringName UpdateSetTextAlign = "update_set_text_align";
        /// <summary>
        /// Cached name for the 'update_set_text_selection' method.
        /// </summary>
        public static readonly StringName UpdateSetTextSelection = "update_set_text_selection";
        /// <summary>
        /// Cached name for the 'update_set_flag' method.
        /// </summary>
        public static readonly StringName UpdateSetFlag = "update_set_flag";
        /// <summary>
        /// Cached name for the 'update_set_classname' method.
        /// </summary>
        public static readonly StringName UpdateSetClassname = "update_set_classname";
        /// <summary>
        /// Cached name for the 'update_set_placeholder' method.
        /// </summary>
        public static readonly StringName UpdateSetPlaceholder = "update_set_placeholder";
        /// <summary>
        /// Cached name for the 'update_set_language' method.
        /// </summary>
        public static readonly StringName UpdateSetLanguage = "update_set_language";
        /// <summary>
        /// Cached name for the 'update_set_text_orientation' method.
        /// </summary>
        public static readonly StringName UpdateSetTextOrientation = "update_set_text_orientation";
        /// <summary>
        /// Cached name for the 'update_set_list_orientation' method.
        /// </summary>
        public static readonly StringName UpdateSetListOrientation = "update_set_list_orientation";
        /// <summary>
        /// Cached name for the 'update_set_shortcut' method.
        /// </summary>
        public static readonly StringName UpdateSetShortcut = "update_set_shortcut";
        /// <summary>
        /// Cached name for the 'update_set_url' method.
        /// </summary>
        public static readonly StringName UpdateSetUrl = "update_set_url";
        /// <summary>
        /// Cached name for the 'update_set_role_description' method.
        /// </summary>
        public static readonly StringName UpdateSetRoleDescription = "update_set_role_description";
        /// <summary>
        /// Cached name for the 'update_set_state_description' method.
        /// </summary>
        public static readonly StringName UpdateSetStateDescription = "update_set_state_description";
        /// <summary>
        /// Cached name for the 'update_set_color_value' method.
        /// </summary>
        public static readonly StringName UpdateSetColorValue = "update_set_color_value";
        /// <summary>
        /// Cached name for the 'update_set_background_color' method.
        /// </summary>
        public static readonly StringName UpdateSetBackgroundColor = "update_set_background_color";
        /// <summary>
        /// Cached name for the 'update_set_foreground_color' method.
        /// </summary>
        public static readonly StringName UpdateSetForegroundColor = "update_set_foreground_color";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public class SignalName
    {
    }
}
