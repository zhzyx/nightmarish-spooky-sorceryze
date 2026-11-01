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
public static partial class GDScriptLanguageProtocol
{
    private static readonly StringName NativeName = "GDScriptLanguageProtocol";

    private static GDScriptLanguageProtocolInstance singleton;

    public static GDScriptLanguageProtocolInstance Singleton =>
        singleton ??= (GDScriptLanguageProtocolInstance)InteropUtils.EngineGetSingleton("GDScriptLanguageProtocol");

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.GetTextDocument, 770545799ul);

    /// <summary>
    /// <para>Returns the language server's <see cref="Godot.GDScriptTextDocument"/> instance.</para>
    /// </summary>
    [Obsolete("'GDScriptTextDocument' is deprecated.")]
    public static GDScriptTextDocument GetTextDocument()
    {
        GDScriptTextDocument ret = (GDScriptTextDocument)NativeCalls.godot_icall_0_87(MethodBind0, GodotObject.GetPtr(Singleton));
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.GetWorkspace, 969295246ul);

    /// <summary>
    /// <para>Returns the language server's <see cref="Godot.GDScriptWorkspace"/> instance.</para>
    /// </summary>
    public static GDScriptWorkspace GetWorkspace()
    {
        GDScriptWorkspace ret = (GDScriptWorkspace)NativeCalls.godot_icall_0_87(MethodBind1, GodotObject.GetPtr(Singleton));
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.IsSmartResolveEnabled, 36873697ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if the language server is providing the smart resolve feature, <see langword="false"/> otherwise. The feature can be configured through the editor settings.</para>
    /// </summary>
    public static bool IsSmartResolveEnabled()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind2, GodotObject.GetPtr(Singleton)).ToBool();
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.IsInitialized, 36873697ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if the language server was initialized by a language server client, <see langword="false"/> otherwise.</para>
    /// </summary>
    public static bool IsInitialized()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind3, GodotObject.GetPtr(Singleton)).ToBool();
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.Initialize, 3762224011ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public static Variant Initialize(Godot.Collections.Dictionary @params)
    {
        Variant ret = EditorNativeCalls.godot_icall_1_657(MethodBind4, GodotObject.GetPtr(Singleton), (godot_dictionary)(@params ?? new()).NativeValue);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.Initialized, 1114965689ul);

    [Obsolete("Accessing LSP endpoints directly might lead to unwanted side effects. Connect to the server via TCP, like a regular language server client.")]
    public static void Initialized(Variant @params)
    {
        NativeCalls.godot_icall_1_658(MethodBind5, GodotObject.GetPtr(Singleton), @params);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.OnClientConnected, 166280745ul);

    [Obsolete("Might result in unwanted side effects for connected clients.")]
    public static Error OnClientConnected()
    {
        Error ret = (Error)NativeCalls.godot_icall_0_39(MethodBind6, GodotObject.GetPtr(Singleton));
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.OnClientDisconnected, 1286410249ul);

    [Obsolete("Might result in unwanted side effects for connected clients.")]
    public static void OnClientDisconnected(int clientId)
    {
        NativeCalls.godot_icall_1_38(MethodBind7, GodotObject.GetPtr(Singleton), clientId);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.NotifyClient, 2511212011ul);

    [Obsolete("Might result in unwanted side effects for connected clients.")]
    public static void NotifyClient(string method, Variant @params = default, int clientId = -1)
    {
        EditorNativeCalls.godot_icall_3_659(MethodBind8, GodotObject.GetPtr(Singleton), method, @params, clientId);
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
    public class SignalName
    {
    }
}
