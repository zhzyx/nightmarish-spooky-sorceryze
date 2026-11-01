namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>Provides language server functionality related to documents.</para>
/// </summary>
[Obsolete("This class is deprecated.")]
public partial class GDScriptTextDocument : RefCounted
{
    private static readonly System.Type CachedType = typeof(GDScriptTextDocument);

    private static readonly StringName NativeName = "GDScriptTextDocument";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public GDScriptTextDocument() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal GDScriptTextDocument(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal GDScriptTextDocument(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.ShowNativeSymbolInEditor, 83702148ul);

    [Obsolete("Use 'Godot.ScriptEditor.GotoHelp(string)' instead.")]
    public void ShowNativeSymbolInEditor(string symbolId)
    {
        NativeCalls.godot_icall_1_57(MethodBind0, GodotObject.GetPtr(this), symbolId);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.DidOpen, 1114965689ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public void DidOpen(Variant @params)
    {
        NativeCalls.godot_icall_1_658(MethodBind1, GodotObject.GetPtr(this), @params);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.DidClose, 1114965689ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public void DidClose(Variant @params)
    {
        NativeCalls.godot_icall_1_658(MethodBind2, GodotObject.GetPtr(this), @params);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.DidChange, 1114965689ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public void DidChange(Variant @params)
    {
        NativeCalls.godot_icall_1_658(MethodBind3, GodotObject.GetPtr(this), @params);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.WillSaveWaitUntil, 1114965689ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public void WillSaveWaitUntil(Variant @params)
    {
        NativeCalls.godot_icall_1_658(MethodBind4, GodotObject.GetPtr(this), @params);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.DidSave, 1114965689ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public void DidSave(Variant @params)
    {
        NativeCalls.godot_icall_1_658(MethodBind5, GodotObject.GetPtr(this), @params);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.NativeSymbol, 3762224011ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public Variant NativeSymbol(Godot.Collections.Dictionary @params)
    {
        Variant ret = EditorNativeCalls.godot_icall_1_657(MethodBind6, GodotObject.GetPtr(this), (godot_dictionary)(@params ?? new()).NativeValue);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.DocumentSymbol, 3877611628ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public Godot.Collections.Array DocumentSymbol(Godot.Collections.Dictionary @params)
    {
        Godot.Collections.Array ret = EditorNativeCalls.godot_icall_1_660(MethodBind7, GodotObject.GetPtr(this), (godot_dictionary)(@params ?? new()).NativeValue);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = ClassDB_get_method_with_compatibility(NativeName, MethodName.Completion, 3877611628ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public Godot.Collections.Array Completion(Godot.Collections.Dictionary @params)
    {
        Godot.Collections.Array ret = EditorNativeCalls.godot_icall_1_660(MethodBind8, GodotObject.GetPtr(this), (godot_dictionary)(@params ?? new()).NativeValue);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind9 = ClassDB_get_method_with_compatibility(NativeName, MethodName.Resolve, 1333564645ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public Godot.Collections.Dictionary Resolve(Godot.Collections.Dictionary @params)
    {
        Godot.Collections.Dictionary ret = EditorNativeCalls.godot_icall_1_661(MethodBind9, GodotObject.GetPtr(this), (godot_dictionary)(@params ?? new()).NativeValue);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind10 = ClassDB_get_method_with_compatibility(NativeName, MethodName.Rename, 1333564645ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public Godot.Collections.Dictionary Rename(Godot.Collections.Dictionary @params)
    {
        Godot.Collections.Dictionary ret = EditorNativeCalls.godot_icall_1_661(MethodBind10, GodotObject.GetPtr(this), (godot_dictionary)(@params ?? new()).NativeValue);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind11 = ClassDB_get_method_with_compatibility(NativeName, MethodName.PrepareRename, 3762224011ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public Variant PrepareRename(Godot.Collections.Dictionary @params)
    {
        Variant ret = EditorNativeCalls.godot_icall_1_657(MethodBind11, GodotObject.GetPtr(this), (godot_dictionary)(@params ?? new()).NativeValue);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind12 = ClassDB_get_method_with_compatibility(NativeName, MethodName.References, 3877611628ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public Godot.Collections.Array References(Godot.Collections.Dictionary @params)
    {
        Godot.Collections.Array ret = EditorNativeCalls.godot_icall_1_660(MethodBind12, GodotObject.GetPtr(this), (godot_dictionary)(@params ?? new()).NativeValue);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind13 = ClassDB_get_method_with_compatibility(NativeName, MethodName.DocumentLink, 3877611628ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public Godot.Collections.Array DocumentLink(Godot.Collections.Dictionary @params)
    {
        Godot.Collections.Array ret = EditorNativeCalls.godot_icall_1_660(MethodBind13, GodotObject.GetPtr(this), (godot_dictionary)(@params ?? new()).NativeValue);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind14 = ClassDB_get_method_with_compatibility(NativeName, MethodName.Hover, 3762224011ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public Variant Hover(Godot.Collections.Dictionary @params)
    {
        Variant ret = EditorNativeCalls.godot_icall_1_657(MethodBind14, GodotObject.GetPtr(this), (godot_dictionary)(@params ?? new()).NativeValue);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind15 = ClassDB_get_method_with_compatibility(NativeName, MethodName.Definition, 3877611628ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public Godot.Collections.Array Definition(Godot.Collections.Dictionary @params)
    {
        Godot.Collections.Array ret = EditorNativeCalls.godot_icall_1_660(MethodBind15, GodotObject.GetPtr(this), (godot_dictionary)(@params ?? new()).NativeValue);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind16 = ClassDB_get_method_with_compatibility(NativeName, MethodName.Declaration, 3762224011ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public Variant Declaration(Godot.Collections.Dictionary @params)
    {
        Variant ret = EditorNativeCalls.godot_icall_1_657(MethodBind16, GodotObject.GetPtr(this), (godot_dictionary)(@params ?? new()).NativeValue);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind17 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SignatureHelp, 3762224011ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public Variant SignatureHelp(Godot.Collections.Dictionary @params)
    {
        Variant ret = EditorNativeCalls.godot_icall_1_657(MethodBind17, GodotObject.GetPtr(this), (godot_dictionary)(@params ?? new()).NativeValue);
        global::System.GC.KeepAlive(this);
        return ret;
    }

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
        /// Cached name for the 'show_native_symbol_in_editor' method.
        /// </summary>
        public static readonly StringName ShowNativeSymbolInEditor = "show_native_symbol_in_editor";
        /// <summary>
        /// Cached name for the 'didOpen' method.
        /// </summary>
        public static readonly StringName DidOpen = "didOpen";
        /// <summary>
        /// Cached name for the 'didClose' method.
        /// </summary>
        public static readonly StringName DidClose = "didClose";
        /// <summary>
        /// Cached name for the 'didChange' method.
        /// </summary>
        public static readonly StringName DidChange = "didChange";
        /// <summary>
        /// Cached name for the 'willSaveWaitUntil' method.
        /// </summary>
        public static readonly StringName WillSaveWaitUntil = "willSaveWaitUntil";
        /// <summary>
        /// Cached name for the 'didSave' method.
        /// </summary>
        public static readonly StringName DidSave = "didSave";
        /// <summary>
        /// Cached name for the 'nativeSymbol' method.
        /// </summary>
        public static readonly StringName NativeSymbol = "nativeSymbol";
        /// <summary>
        /// Cached name for the 'documentSymbol' method.
        /// </summary>
        public static readonly StringName DocumentSymbol = "documentSymbol";
        /// <summary>
        /// Cached name for the 'completion' method.
        /// </summary>
        public static readonly StringName Completion = "completion";
        /// <summary>
        /// Cached name for the 'resolve' method.
        /// </summary>
        public static readonly StringName Resolve = "resolve";
        /// <summary>
        /// Cached name for the 'rename' method.
        /// </summary>
        public static readonly StringName Rename = "rename";
        /// <summary>
        /// Cached name for the 'prepareRename' method.
        /// </summary>
        public static readonly StringName PrepareRename = "prepareRename";
        /// <summary>
        /// Cached name for the 'references' method.
        /// </summary>
        public static readonly StringName References = "references";
        /// <summary>
        /// Cached name for the 'documentLink' method.
        /// </summary>
        public static readonly StringName DocumentLink = "documentLink";
        /// <summary>
        /// Cached name for the 'hover' method.
        /// </summary>
        public static readonly StringName Hover = "hover";
        /// <summary>
        /// Cached name for the 'definition' method.
        /// </summary>
        public static readonly StringName Definition = "definition";
        /// <summary>
        /// Cached name for the 'declaration' method.
        /// </summary>
        public static readonly StringName Declaration = "declaration";
        /// <summary>
        /// Cached name for the 'signatureHelp' method.
        /// </summary>
        public static readonly StringName SignatureHelp = "signatureHelp";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : RefCounted.SignalName
    {
    }
}
