namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>Provides access to certain features that are implemented in the language server.</para>
/// <para><b>Note:</b> This class is not a language server client that can be used to access LSP functionality. It only provides access to a limited set of features that is implemented using the same technical foundation as the language server.</para>
/// </summary>
[GodotClassName("GDScriptLanguageProtocol")]
public partial class GDScriptLanguageProtocolInstance : JsonRpc
{
    private static readonly System.Type CachedType = typeof(GDScriptLanguageProtocolInstance);

    private static readonly StringName NativeName = "GDScriptLanguageProtocol";

    internal GDScriptLanguageProtocolInstance() : this(false)
    {
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal GDScriptLanguageProtocolInstance(IntPtr ptr) : this(false)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal GDScriptLanguageProtocolInstance(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetTextDocument, 770545799ul);

    /// <summary>
    /// <para>Returns the language server's <see cref="Godot.GDScriptTextDocument"/> instance.</para>
    /// </summary>
    [Obsolete("'GDScriptTextDocument' is deprecated.")]
    public GDScriptTextDocument GetTextDocument()
    {
        GDScriptTextDocument ret = (GDScriptTextDocument)NativeCalls.godot_icall_0_87(MethodBind0, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetWorkspace, 969295246ul);

    /// <summary>
    /// <para>Returns the language server's <see cref="Godot.GDScriptWorkspace"/> instance.</para>
    /// </summary>
    public GDScriptWorkspace GetWorkspace()
    {
        GDScriptWorkspace ret = (GDScriptWorkspace)NativeCalls.godot_icall_0_87(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsSmartResolveEnabled, 36873697ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if the language server is providing the smart resolve feature, <see langword="false"/> otherwise. The feature can be configured through the editor settings.</para>
    /// </summary>
    public bool IsSmartResolveEnabled()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind2, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsInitialized, 36873697ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if the language server was initialized by a language server client, <see langword="false"/> otherwise.</para>
    /// </summary>
    public bool IsInitialized()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind3, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.Initialize, 3762224011ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public Variant Initialize(Godot.Collections.Dictionary @params)
    {
        Variant ret = EditorNativeCalls.godot_icall_1_657(MethodBind4, GodotObject.GetPtr(this), (godot_dictionary)(@params ?? new()).NativeValue);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.Initialized, 1114965689ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public void Initialized(Variant @params)
    {
        NativeCalls.godot_icall_1_658(MethodBind5, GodotObject.GetPtr(this), @params);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.OnClientConnected, 166280745ul);

    [Obsolete("Might result in unwanted side effects for connected clients.")]
    public Error OnClientConnected()
    {
        Error ret = (Error)NativeCalls.godot_icall_0_39(MethodBind6, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.OnClientDisconnected, 1286410249ul);

    [Obsolete("Might result in unwanted side effects for connected clients.")]
    public void OnClientDisconnected(int clientId)
    {
        NativeCalls.godot_icall_1_38(MethodBind7, GodotObject.GetPtr(this), clientId);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = ClassDB_get_method_with_compatibility(NativeName, MethodName.NotifyClient, 2511212011ul);

    [Obsolete("Might result in unwanted side effects for connected clients.")]
    public void NotifyClient(string method, Variant @params = default, int clientId = -1)
    {
        EditorNativeCalls.godot_icall_3_659(MethodBind8, GodotObject.GetPtr(this), method, @params, clientId);
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
    public new class PropertyName : JsonRpc.PropertyName
    {
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : JsonRpc.MethodName
    {
        /// <summary>
        /// Cached name for the 'get_text_document' method.
        /// </summary>
        public static readonly StringName GetTextDocument = "get_text_document";
        /// <summary>
        /// Cached name for the 'get_workspace' method.
        /// </summary>
        public static readonly StringName GetWorkspace = "get_workspace";
        /// <summary>
        /// Cached name for the 'is_smart_resolve_enabled' method.
        /// </summary>
        public static readonly StringName IsSmartResolveEnabled = "is_smart_resolve_enabled";
        /// <summary>
        /// Cached name for the 'is_initialized' method.
        /// </summary>
        public static readonly StringName IsInitialized = "is_initialized";
        /// <summary>
        /// Cached name for the 'initialize' method.
        /// </summary>
        public static readonly StringName Initialize = "initialize";
        /// <summary>
        /// Cached name for the 'initialized' method.
        /// </summary>
        public static readonly StringName Initialized = "initialized";
        /// <summary>
        /// Cached name for the 'on_client_connected' method.
        /// </summary>
        public static readonly StringName OnClientConnected = "on_client_connected";
        /// <summary>
        /// Cached name for the 'on_client_disconnected' method.
        /// </summary>
        public static readonly StringName OnClientDisconnected = "on_client_disconnected";
        /// <summary>
        /// Cached name for the 'notify_client' method.
        /// </summary>
        public static readonly StringName NotifyClient = "notify_client";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : JsonRpc.SignalName
    {
    }
}
