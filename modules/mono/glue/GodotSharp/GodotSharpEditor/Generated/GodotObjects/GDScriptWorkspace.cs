namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>Provides language server functionality related to the workspace.</para>
/// </summary>
public partial class GDScriptWorkspace : RefCounted
{
    private static readonly System.Type CachedType = typeof(GDScriptWorkspace);

    private static readonly StringName NativeName = "GDScriptWorkspace";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public GDScriptWorkspace() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal GDScriptWorkspace(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal GDScriptWorkspace(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.ApplyNewSignal, 3682583557ul);

    [Obsolete("Might result in unwanted side effects for connected clients.")]
    public void ApplyNewSignal(GodotObject obj, string function, string[] args)
    {
        EditorNativeCalls.godot_icall_3_662(MethodBind0, GodotObject.GetPtr(this), GodotObject.GetPtr(obj), function, args);
        global::System.GC.KeepAlive(this);
    }

    [Obsolete("Might result in unwanted side effects for connected clients.")]
    public void ApplyNewSignal(GodotObject obj, string function, ReadOnlySpan<string> args)
    {
        EditorNativeCalls.godot_icall_3_662(MethodBind0, GodotObject.GetPtr(this), GodotObject.GetPtr(obj), function, args);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetFilePath, 1703090593ul);

    /// <summary>
    /// <para>Converts a URI to a file path.</para>
    /// </summary>
    public string GetFilePath(string uri)
    {
        string ret = NativeCalls.godot_icall_1_332(MethodBind1, GodotObject.GetPtr(this), uri);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetFileUri, 3135753539ul);

    /// <summary>
    /// <para>Converts a file path to a URI.</para>
    /// </summary>
    public string GetFileUri(string path)
    {
        string ret = NativeCalls.godot_icall_1_332(MethodBind2, GodotObject.GetPtr(this), path);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GenerateScriptApi, 2786125124ul);

    /// <summary>
    /// <para>Returns the interface of the script in a machine-readable format.</para>
    /// </summary>
    public Godot.Collections.Dictionary GenerateScriptApi(string path)
    {
        Godot.Collections.Dictionary ret = EditorNativeCalls.godot_icall_1_484(MethodBind3, GodotObject.GetPtr(this), path);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.DidDeleteFiles, 4155329257ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public void DidDeleteFiles(Godot.Collections.Dictionary @params)
    {
        NativeCalls.godot_icall_1_147(MethodBind4, GodotObject.GetPtr(this), (godot_dictionary)(@params ?? new()).NativeValue);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.ParseScript, 852856452ul);

    [Obsolete("Might result in unwanted side effects for connected clients.")]
    public Error ParseScript(string path, string content)
    {
        Error ret = (Error)NativeCalls.godot_icall_2_360(MethodBind5, GodotObject.GetPtr(this), path, content);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.ParseLocalScript, 166001499ul);

    [Obsolete("Might result in unwanted side effects for connected clients.")]
    public Error ParseLocalScript(string path)
    {
        Error ret = (Error)NativeCalls.godot_icall_1_159(MethodBind6, GodotObject.GetPtr(this), path);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.PublishDiagnostics, 83702148ul);

    [Obsolete("Might result in unwanted side effects for connected clients.")]
    public void PublishDiagnostics(string path)
    {
        NativeCalls.godot_icall_1_57(MethodBind7, GodotObject.GetPtr(this), path);
        global::System.GC.KeepAlive(this);
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
        /// Cached name for the 'apply_new_signal' method.
        /// </summary>
        public static readonly StringName ApplyNewSignal = "apply_new_signal";
        /// <summary>
        /// Cached name for the 'get_file_path' method.
        /// </summary>
        public static readonly StringName GetFilePath = "get_file_path";
        /// <summary>
        /// Cached name for the 'get_file_uri' method.
        /// </summary>
        public static readonly StringName GetFileUri = "get_file_uri";
        /// <summary>
        /// Cached name for the 'generate_script_api' method.
        /// </summary>
        public static readonly StringName GenerateScriptApi = "generate_script_api";
        /// <summary>
        /// Cached name for the 'didDeleteFiles' method.
        /// </summary>
        public static readonly StringName DidDeleteFiles = "didDeleteFiles";
        /// <summary>
        /// Cached name for the 'parse_script' method.
        /// </summary>
        public static readonly StringName ParseScript = "parse_script";
        /// <summary>
        /// Cached name for the 'parse_local_script' method.
        /// </summary>
        public static readonly StringName ParseLocalScript = "parse_local_script";
        /// <summary>
        /// Cached name for the 'publish_diagnostics' method.
        /// </summary>
        public static readonly StringName PublishDiagnostics = "publish_diagnostics";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : RefCounted.SignalName
    {
    }
}
