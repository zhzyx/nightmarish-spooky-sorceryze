namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>Base editor for editing scripts in the <see cref="Godot.ScriptEditor"/>. This does not include documentation items.</para>
/// </summary>
public partial class ScriptEditorBase : VBoxContainer
{
    private static readonly System.Type CachedType = typeof(ScriptEditorBase);

    private static readonly StringName NativeName = "ScriptEditorBase";

    internal ScriptEditorBase() : this(false)
    {
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal ScriptEditorBase(IntPtr ptr) : this(false)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal ScriptEditorBase(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.AddSyntaxHighlighter, 1092774468ul);

    /// <summary>
    /// <para>Adds an <see cref="Godot.EditorSyntaxHighlighter"/> to the open script.</para>
    /// </summary>
    public void AddSyntaxHighlighter(EditorSyntaxHighlighter highlighter)
    {
        NativeCalls.godot_icall_1_56(MethodBind0, GodotObject.GetPtr(this), GodotObject.GetPtr(highlighter));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetBaseEditor, 2783021301ul);

    /// <summary>
    /// <para>Returns the underlying <see cref="Godot.Control"/> used for editing scripts. For text scripts, this is a <see cref="Godot.CodeEdit"/>.</para>
    /// </summary>
    public Control GetBaseEditor()
    {
        Control ret = (Control)NativeCalls.godot_icall_0_53(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    /// <summary>
    /// <para>Emitted after script validation or when the edited resource has changed.</para>
    /// </summary>
    [Obsolete("This signal should only be used internally.")]
    public event Action NameChanged
    {
        add => Connect(SignalName.NameChanged, Callable.From(value));
        remove => Disconnect(SignalName.NameChanged, Callable.From(value));
    }

    [Obsolete("This signal should only be used internally.")]
    protected void EmitSignalNameChanged()
    {
        EmitSignal(SignalName.NameChanged);
    }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.ScriptEditorBase.RequestHelp"/> event of a <see cref="Godot.ScriptEditorBase"/> class.
    /// </summary>
    [Obsolete("This signal should only be used internally.")]
    public delegate void RequestHelpEventHandler(string topic);

    [Obsolete("This signal should only be used internally.")]
    private static void RequestHelpTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 1);
        ((RequestHelpEventHandler)delegateObj)(VariantUtils.ConvertTo<string>(args[0]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted when the user requests contextual help.</para>
    /// </summary>
    [Obsolete("This signal should only be used internally.")]
    public unsafe event RequestHelpEventHandler RequestHelp
    {
        add => Connect(SignalName.RequestHelp, Callable.CreateWithUnsafeTrampoline(value, &RequestHelpTrampoline));
        remove => Disconnect(SignalName.RequestHelp, Callable.CreateWithUnsafeTrampoline(value, &RequestHelpTrampoline));
    }

    [Obsolete("This signal should only be used internally.")]
    protected void EmitSignalRequestHelp(string topic)
    {
        EmitSignal(SignalName.RequestHelp, topic);
    }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.ScriptEditorBase.RequestOpenScriptAtLine"/> event of a <see cref="Godot.ScriptEditorBase"/> class.
    /// </summary>
    [Obsolete("This signal should only be used internally. See 'Godot.EditorInterface.EditScript(Script, int, int, bool)' instead.")]
    public delegate void RequestOpenScriptAtLineEventHandler(GodotObject script, long line);

    [Obsolete("This signal should only be used internally. See 'Godot.EditorInterface.EditScript(Script, int, int, bool)' instead.")]
    private static void RequestOpenScriptAtLineTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 2);
        ((RequestOpenScriptAtLineEventHandler)delegateObj)(VariantUtils.ConvertTo<GodotObject>(args[0]), VariantUtils.ConvertTo<long>(args[1]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted when the user requests to view a specific line of a script, similar to <see cref="Godot.ScriptEditorBase.GoToMethod"/>.</para>
    /// </summary>
    [Obsolete("This signal should only be used internally. See 'Godot.EditorInterface.EditScript(Script, int, int, bool)' instead.")]
    public unsafe event RequestOpenScriptAtLineEventHandler RequestOpenScriptAtLine
    {
        add => Connect(SignalName.RequestOpenScriptAtLine, Callable.CreateWithUnsafeTrampoline(value, &RequestOpenScriptAtLineTrampoline));
        remove => Disconnect(SignalName.RequestOpenScriptAtLine, Callable.CreateWithUnsafeTrampoline(value, &RequestOpenScriptAtLineTrampoline));
    }

    [Obsolete("This signal should only be used internally. See 'Godot.EditorInterface.EditScript(Script, int, int, bool)' instead.")]
    protected void EmitSignalRequestOpenScriptAtLine(GodotObject script, long line)
    {
        EmitSignal(SignalName.RequestOpenScriptAtLine, script, line);
    }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.ScriptEditorBase.GoToHelp"/> event of a <see cref="Godot.ScriptEditorBase"/> class.
    /// </summary>
    [Obsolete("This signal should only be used internally. See 'Godot.ScriptEditor.GotoHelp(string)' instead.")]
    public delegate void GoToHelpEventHandler(string what);

    [Obsolete("This signal should only be used internally. See 'Godot.ScriptEditor.GotoHelp(string)' instead.")]
    private static void GoToHelpTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 1);
        ((GoToHelpEventHandler)delegateObj)(VariantUtils.ConvertTo<string>(args[0]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted when the user requests a specific documentation page.</para>
    /// </summary>
    [Obsolete("This signal should only be used internally. See 'Godot.ScriptEditor.GotoHelp(string)' instead.")]
    public unsafe event GoToHelpEventHandler GoToHelp
    {
        add => Connect(SignalName.GoToHelp, Callable.CreateWithUnsafeTrampoline(value, &GoToHelpTrampoline));
        remove => Disconnect(SignalName.GoToHelp, Callable.CreateWithUnsafeTrampoline(value, &GoToHelpTrampoline));
    }

    [Obsolete("This signal should only be used internally. See 'Godot.ScriptEditor.GotoHelp(string)' instead.")]
    protected void EmitSignalGoToHelp(string what)
    {
        EmitSignal(SignalName.GoToHelp, what);
    }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.ScriptEditorBase.GoToMethod"/> event of a <see cref="Godot.ScriptEditorBase"/> class.
    /// </summary>
    [Obsolete("This signal should only be used internally.")]
    public delegate void GoToMethodEventHandler(GodotObject script, string method);

    [Obsolete("This signal should only be used internally.")]
    private static void GoToMethodTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 2);
        ((GoToMethodEventHandler)delegateObj)(VariantUtils.ConvertTo<GodotObject>(args[0]), VariantUtils.ConvertTo<string>(args[1]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted when the user requests to view a specific method of a script, similar to <see cref="Godot.ScriptEditorBase.RequestOpenScriptAtLine"/>.</para>
    /// </summary>
    [Obsolete("This signal should only be used internally.")]
    public unsafe event GoToMethodEventHandler GoToMethod
    {
        add => Connect(SignalName.GoToMethod, Callable.CreateWithUnsafeTrampoline(value, &GoToMethodTrampoline));
        remove => Disconnect(SignalName.GoToMethod, Callable.CreateWithUnsafeTrampoline(value, &GoToMethodTrampoline));
    }

    [Obsolete("This signal should only be used internally.")]
    protected void EmitSignalGoToMethod(GodotObject script, string method)
    {
        EmitSignal(SignalName.GoToMethod, script, method);
    }

    /// <summary>
    /// <para>Emitted when the editor requests to save a new history navigation point.</para>
    /// </summary>
    [Obsolete("This signal should only be used internally.")]
    public event Action RequestSaveHistory
    {
        add => Connect(SignalName.RequestSaveHistory, Callable.From(value));
        remove => Disconnect(SignalName.RequestSaveHistory, Callable.From(value));
    }

    [Obsolete("This signal should only be used internally.")]
    protected void EmitSignalRequestSaveHistory()
    {
        EmitSignal(SignalName.RequestSaveHistory);
    }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.ScriptEditorBase.RequestSavePreviousState"/> event of a <see cref="Godot.ScriptEditorBase"/> class.
    /// </summary>
    [Obsolete("This signal should only be used internally.")]
    public delegate void RequestSavePreviousStateEventHandler(Godot.Collections.Dictionary state);

    [Obsolete("This signal should only be used internally.")]
    private static void RequestSavePreviousStateTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 1);
        ((RequestSavePreviousStateEventHandler)delegateObj)(VariantUtils.ConvertTo<Godot.Collections.Dictionary>(args[0]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted when the editor requests an update to its navigation point.</para>
    /// </summary>
    [Obsolete("This signal should only be used internally.")]
    public unsafe event RequestSavePreviousStateEventHandler RequestSavePreviousState
    {
        add => Connect(SignalName.RequestSavePreviousState, Callable.CreateWithUnsafeTrampoline(value, &RequestSavePreviousStateTrampoline));
        remove => Disconnect(SignalName.RequestSavePreviousState, Callable.CreateWithUnsafeTrampoline(value, &RequestSavePreviousStateTrampoline));
    }

    [Obsolete("This signal should only be used internally.")]
    protected void EmitSignalRequestSavePreviousState(Godot.Collections.Dictionary state)
    {
        EmitSignal(SignalName.RequestSavePreviousState, state);
    }

    /// <summary>
    /// <para>Emitted after script validation.</para>
    /// </summary>
    [Obsolete("This signal should only be used internally.")]
    public event Action EditedScriptChanged
    {
        add => Connect(SignalName.EditedScriptChanged, Callable.From(value));
        remove => Disconnect(SignalName.EditedScriptChanged, Callable.From(value));
    }

    [Obsolete("This signal should only be used internally.")]
    protected void EmitSignalEditedScriptChanged()
    {
        EmitSignal(SignalName.EditedScriptChanged);
    }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.ScriptEditorBase.SearchInFilesRequested"/> event of a <see cref="Godot.ScriptEditorBase"/> class.
    /// </summary>
    [Obsolete("This signal should only be used internally.")]
    public delegate void SearchInFilesRequestedEventHandler(string text);

    [Obsolete("This signal should only be used internally.")]
    private static void SearchInFilesRequestedTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 1);
        ((SearchInFilesRequestedEventHandler)delegateObj)(VariantUtils.ConvertTo<string>(args[0]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted when the user request to search text in the file system.</para>
    /// </summary>
    [Obsolete("This signal should only be used internally.")]
    public unsafe event SearchInFilesRequestedEventHandler SearchInFilesRequested
    {
        add => Connect(SignalName.SearchInFilesRequested, Callable.CreateWithUnsafeTrampoline(value, &SearchInFilesRequestedTrampoline));
        remove => Disconnect(SignalName.SearchInFilesRequested, Callable.CreateWithUnsafeTrampoline(value, &SearchInFilesRequestedTrampoline));
    }

    [Obsolete("This signal should only be used internally.")]
    protected void EmitSignalSearchInFilesRequested(string text)
    {
        EmitSignal(SignalName.SearchInFilesRequested, text);
    }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.ScriptEditorBase.ReplaceInFilesRequested"/> event of a <see cref="Godot.ScriptEditorBase"/> class.
    /// </summary>
    [Obsolete("This signal should only be used internally.")]
    public delegate void ReplaceInFilesRequestedEventHandler(string text);

    [Obsolete("This signal should only be used internally.")]
    private static void ReplaceInFilesRequestedTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 1);
        ((ReplaceInFilesRequestedEventHandler)delegateObj)(VariantUtils.ConvertTo<string>(args[0]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted when the user request to find and replace text in the file system.</para>
    /// </summary>
    [Obsolete("This signal should only be used internally.")]
    public unsafe event ReplaceInFilesRequestedEventHandler ReplaceInFilesRequested
    {
        add => Connect(SignalName.ReplaceInFilesRequested, Callable.CreateWithUnsafeTrampoline(value, &ReplaceInFilesRequestedTrampoline));
        remove => Disconnect(SignalName.ReplaceInFilesRequested, Callable.CreateWithUnsafeTrampoline(value, &ReplaceInFilesRequestedTrampoline));
    }

    [Obsolete("This signal should only be used internally.")]
    protected void EmitSignalReplaceInFilesRequested(string text)
    {
        EmitSignal(SignalName.ReplaceInFilesRequested, text);
    }

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_name_changed = "NameChanged";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_request_help = "RequestHelp";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_request_open_script_at_line = "RequestOpenScriptAtLine";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_go_to_help = "GoToHelp";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_go_to_method = "GoToMethod";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_request_save_history = "RequestSaveHistory";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_request_save_previous_state = "RequestSavePreviousState";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_edited_script_changed = "EditedScriptChanged";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_search_in_files_requested = "SearchInFilesRequested";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_replace_in_files_requested = "ReplaceInFilesRequested";

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
        if (signal == SignalName.NameChanged)
        {
            if (HasGodotClassSignal(SignalProxyName_name_changed.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.RequestHelp)
        {
            if (HasGodotClassSignal(SignalProxyName_request_help.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.RequestOpenScriptAtLine)
        {
            if (HasGodotClassSignal(SignalProxyName_request_open_script_at_line.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.GoToHelp)
        {
            if (HasGodotClassSignal(SignalProxyName_go_to_help.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.GoToMethod)
        {
            if (HasGodotClassSignal(SignalProxyName_go_to_method.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.RequestSaveHistory)
        {
            if (HasGodotClassSignal(SignalProxyName_request_save_history.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.RequestSavePreviousState)
        {
            if (HasGodotClassSignal(SignalProxyName_request_save_previous_state.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.EditedScriptChanged)
        {
            if (HasGodotClassSignal(SignalProxyName_edited_script_changed.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.SearchInFilesRequested)
        {
            if (HasGodotClassSignal(SignalProxyName_search_in_files_requested.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.ReplaceInFilesRequested)
        {
            if (HasGodotClassSignal(SignalProxyName_replace_in_files_requested.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        return base.HasGodotClassSignal(signal);
    }

    /// <summary>
    /// Cached StringNames for the properties and fields contained in this class, for fast lookup.
    /// </summary>
    public new class PropertyName : VBoxContainer.PropertyName
    {
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : VBoxContainer.MethodName
    {
        /// <summary>
        /// Cached name for the 'add_syntax_highlighter' method.
        /// </summary>
        public static readonly StringName AddSyntaxHighlighter = "add_syntax_highlighter";
        /// <summary>
        /// Cached name for the 'get_base_editor' method.
        /// </summary>
        public static readonly StringName GetBaseEditor = "get_base_editor";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : VBoxContainer.SignalName
    {
        /// <summary>
        /// Cached name for the 'name_changed' signal.
        /// </summary>
        public static readonly StringName NameChanged = "name_changed";
        /// <summary>
        /// Cached name for the 'request_help' signal.
        /// </summary>
        public static readonly StringName RequestHelp = "request_help";
        /// <summary>
        /// Cached name for the 'request_open_script_at_line' signal.
        /// </summary>
        public static readonly StringName RequestOpenScriptAtLine = "request_open_script_at_line";
        /// <summary>
        /// Cached name for the 'go_to_help' signal.
        /// </summary>
        public static readonly StringName GoToHelp = "go_to_help";
        /// <summary>
        /// Cached name for the 'go_to_method' signal.
        /// </summary>
        public static readonly StringName GoToMethod = "go_to_method";
        /// <summary>
        /// Cached name for the 'request_save_history' signal.
        /// </summary>
        public static readonly StringName RequestSaveHistory = "request_save_history";
        /// <summary>
        /// Cached name for the 'request_save_previous_state' signal.
        /// </summary>
        public static readonly StringName RequestSavePreviousState = "request_save_previous_state";
        /// <summary>
        /// Cached name for the 'edited_script_changed' signal.
        /// </summary>
        public static readonly StringName EditedScriptChanged = "edited_script_changed";
        /// <summary>
        /// Cached name for the 'search_in_files_requested' signal.
        /// </summary>
        public static readonly StringName SearchInFilesRequested = "search_in_files_requested";
        /// <summary>
        /// Cached name for the 'replace_in_files_requested' signal.
        /// </summary>
        public static readonly StringName ReplaceInFilesRequested = "replace_in_files_requested";
    }
}
