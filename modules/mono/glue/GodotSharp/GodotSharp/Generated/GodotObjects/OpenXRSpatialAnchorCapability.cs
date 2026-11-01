namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>This is an internal class that handles the OpenXR anchor spatial entity extension.</para>
/// </summary>
public partial class OpenXRSpatialAnchorCapability : OpenXRExtensionWrapper
{
    public enum PersistenceScope : long
    {
        /// <summary>
        /// <para>Provides the application with read-only access (i.e. application cannot modify this scope) to spatial entities persisted and managed by the system. The application can use the UUID in the persistence component for this scope to correlate entities across spatial contexts and device reboots.</para>
        /// </summary>
        SystemManaged = 1,
        /// <summary>
        /// <para>Persistence operations and data access is limited to spatial anchors, on the same device, for the same user and same app (using <see cref="Godot.OpenXRSpatialAnchorCapability.PersistAnchor(OpenXRAnchorTracker, Rid, Callable)"/> and <see cref="Godot.OpenXRSpatialAnchorCapability.UnpersistAnchor(OpenXRAnchorTracker, Rid, Callable)"/> functions)</para>
        /// </summary>
        LocalAnchors = 1000781000
    }

    private static readonly System.Type CachedType = typeof(OpenXRSpatialAnchorCapability);

    private static readonly StringName NativeName = "OpenXRSpatialAnchorCapability";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public OpenXRSpatialAnchorCapability() : this(false)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: false);
        }
    }

    internal OpenXRSpatialAnchorCapability(IntPtr ptr) : this(false)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal OpenXRSpatialAnchorCapability(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsSpatialAnchorSupported, 2240911060ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if spatial anchors are supported by the hardware. Only returns a valid value after OpenXR has been initialized.</para>
    /// </summary>
    public bool IsSpatialAnchorSupported()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind0, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsSpatialPersistenceSupported, 2240911060ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if persistent spatial anchors are supported by the hardware. Only returns a valid value after OpenXR has been initialized.</para>
    /// </summary>
    public bool IsSpatialPersistenceSupported()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind1, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsPersistenceScopeSupported, 3651771626ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if this persistence scope is supported by our spatial anchor capability.</para>
    /// <para><b>Note:</b> Only valid after an OpenXR instance has been created.</para>
    /// </summary>
    public bool IsPersistenceScopeSupported(OpenXRSpatialAnchorCapability.PersistenceScope scope)
    {
        bool ret = NativeCalls.godot_icall_1_86(MethodBind2, GodotObject.GetPtr(this), (int)scope).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.CreateDefaultPersistenceContext, 1401033661ul);

    /// <summary>
    /// <para>Calls <see cref="Godot.OpenXRSpatialAnchorCapability.CreatePersistenceContext(OpenXRSpatialAnchorCapability.PersistenceScope, Callable)"/> with a configuration that likely works with the XR runtime.</para>
    /// <para><paramref name="userCallback"/> is called when the context is created.</para>
    /// </summary>
    public OpenXRFutureResult CreateDefaultPersistenceContext(Callable userCallback = default)
    {
        OpenXRFutureResult ret = (OpenXRFutureResult)NativeCalls.godot_icall_1_820(MethodBind3, GodotObject.GetPtr(this), userCallback);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.CreatePersistenceContext, 856276630ul);

    /// <summary>
    /// <para>Creates a new persistence context for storing persistent data.</para>
    /// <para><b>Note:</b> This is an asynchronous method and returns an <see cref="Godot.OpenXRFutureResult"/> object with which to track the status, discarding this object will not cancel the creation process. On success <paramref name="userCallback"/> will be called if specified. The result value for this function is the <see cref="Godot.Rid"/> for our persistence context.</para>
    /// </summary>
    public OpenXRFutureResult CreatePersistenceContext(OpenXRSpatialAnchorCapability.PersistenceScope scope, Callable userCallback = default)
    {
        OpenXRFutureResult ret = (OpenXRFutureResult)NativeCalls.godot_icall_2_983(MethodBind4, GodotObject.GetPtr(this), (int)scope, userCallback);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetPersistenceContextHandle, 2198884583ul);

    /// <summary>
    /// <para>Returns the internal handle for this persistence context.</para>
    /// <para><b>Note:</b> For GDExtension implementations.</para>
    /// </summary>
    public ulong GetPersistenceContextHandle(Rid persistenceContext)
    {
        ulong ret = NativeCalls.godot_icall_1_893(MethodBind5, GodotObject.GetPtr(this), persistenceContext);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.FreePersistenceContext, 2722037293ul);

    /// <summary>
    /// <para>Frees a persistence context previously created with <see cref="Godot.OpenXRSpatialAnchorCapability.CreatePersistenceContext(OpenXRSpatialAnchorCapability.PersistenceScope, Callable)"/>.</para>
    /// </summary>
    public void FreePersistenceContext(Rid persistenceContext)
    {
        NativeCalls.godot_icall_1_63(MethodBind6, GodotObject.GetPtr(this), persistenceContext);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.CreateNewAnchor, 4088043487ul);

    /// <summary>
    /// <para>Creates a new anchor that will be tracked by the XR runtime. The <paramref name="transform"/> should be a transform in the local space of your <see cref="Godot.XROrigin3D"/> node. If <paramref name="spatialContext"/> is not specified the default will be used, this requires <c>ProjectSettings.xr/openxr/extensions/spatial_entity/enable_builtin_anchor_detection</c> to be set. The returned tracker will track the location in case our reference space changes.</para>
    /// <para><paramref name="next"/> must be a valid next object for the <c>XrSpatialAnchorCreateInfoEXT</c> chain.</para>
    /// </summary>
    public unsafe OpenXRAnchorTracker CreateNewAnchor(Transform3D transform, Rid spatialContext = default, OpenXRStructureBase next = null)
    {
        OpenXRAnchorTracker ret = (OpenXRAnchorTracker)NativeCalls.godot_icall_3_984(MethodBind7, GodotObject.GetPtr(this), &transform, spatialContext, GodotObject.GetPtr(next));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = ClassDB_get_method_with_compatibility(NativeName, MethodName.RemoveAnchor, 3579451518ul);

    /// <summary>
    /// <para>Remove an anchor previously created with <see cref="Godot.OpenXRSpatialAnchorCapability.CreateNewAnchor(Transform3D, Rid, OpenXRStructureBase)"/>. If this anchor was persistent you must first call <see cref="Godot.OpenXRSpatialAnchorCapability.UnpersistAnchor(OpenXRAnchorTracker, Rid, Callable)"/> and await its callback.</para>
    /// </summary>
    public void RemoveAnchor(OpenXRAnchorTracker anchorTracker)
    {
        NativeCalls.godot_icall_1_56(MethodBind8, GodotObject.GetPtr(this), GodotObject.GetPtr(anchorTracker));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind9 = ClassDB_get_method_with_compatibility(NativeName, MethodName.PersistAnchor, 4244202513ul);

    /// <summary>
    /// <para>Changes this anchor into a persistent anchor. This means its location will be stored on the device and the anchor will be restored the next time your application starts. If <paramref name="persistenceContext"/> is not specified the default will be used, this requires <c>ProjectSettings.xr/openxr/extensions/spatial_entity/enable_builtin_anchor_detection</c> to be set.</para>
    /// <para><b>Note:</b> This is an asynchronous method and returns an <see cref="Godot.OpenXRFutureResult"/> object with which to track the status, discarding this object will not cancel the creation process. On success <paramref name="userCallback"/> will be called if specified. The result value for this function is a boolean which will be set to <see langword="true"/> on successful completion.</para>
    /// </summary>
    public OpenXRFutureResult PersistAnchor(OpenXRAnchorTracker anchorTracker, Rid persistenceContext = default, Callable userCallback = default)
    {
        OpenXRFutureResult ret = (OpenXRFutureResult)NativeCalls.godot_icall_3_985(MethodBind9, GodotObject.GetPtr(this), GodotObject.GetPtr(anchorTracker), persistenceContext, userCallback);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind10 = ClassDB_get_method_with_compatibility(NativeName, MethodName.UnpersistAnchor, 4244202513ul);

    /// <summary>
    /// <para>Removes the persistent data from this anchor. The runtime will not recreate the anchor when your application restarts. If <paramref name="persistenceContext"/> is not specified the default will be used, this requires <c>ProjectSettings.xr/openxr/extensions/spatial_entity/enabled</c> to be set.</para>
    /// <para><b>Note:</b> This is an asynchronous method and returns an <see cref="Godot.OpenXRFutureResult"/> object with which to track the status, discarding this object will not cancel the creation process. On success <paramref name="userCallback"/> will be called if specified. The result value for this function is a boolean which will be set to <see langword="true"/> on successful completion.</para>
    /// </summary>
    public OpenXRFutureResult UnpersistAnchor(OpenXRAnchorTracker anchorTracker, Rid persistenceContext = default, Callable userCallback = default)
    {
        OpenXRFutureResult ret = (OpenXRFutureResult)NativeCalls.godot_icall_3_985(MethodBind10, GodotObject.GetPtr(this), GodotObject.GetPtr(anchorTracker), persistenceContext, userCallback);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind11 = ClassDB_get_method_with_compatibility(NativeName, MethodName.StartEntityDiscovery, 3452714169ul);

    /// <summary>
    /// <para>Calls <see cref="Godot.OpenXRSpatialEntityExtension.DiscoverSpatialEntities(Rid, long[], OpenXRStructureBase, Callable)"/> and <see cref="Godot.OpenXRSpatialEntityExtension.QuerySnapshot(Rid, Godot.Collections.Array{OpenXRSpatialComponentData}, OpenXRStructureBase)"/> with the anchor entities associated with <paramref name="spatialContext"/>.</para>
    /// <para><paramref name="componentData"/> are the <see cref="Godot.OpenXRSpatialComponentData"/>s to discover for this anchor capability.</para>
    /// <para>If <paramref name="nextSnapshotCreate"/> is non-null, then pass this to the <c>next</c> parameter in <see cref="Godot.OpenXRSpatialEntityExtension.DiscoverSpatialEntities(Rid, long[], OpenXRStructureBase, Callable)"/>.</para>
    /// <para>If <paramref name="nextSnapshotQuery"/> is non-null, then pass this to the <c>next</c> parameter in <see cref="Godot.OpenXRSpatialEntityExtension.QuerySnapshot(Rid, Godot.Collections.Array{OpenXRSpatialComponentData}, OpenXRStructureBase)"/>.</para>
    /// <para><paramref name="userCallback"/>, when non-null, is called with two parameters usually twice. The first parameter is the <see cref="Godot.Rid"/> of the discovery snapshot and the second parameter is a boolean where <see langword="false"/> indicates the discovery snapshot is about to be processed, and <see langword="true"/> indicates the discovery snapshot has been processed and <paramref name="componentData"/> has valid data. The second call is skipped if an error was encountered.</para>
    /// <para>The returned <see cref="Godot.OpenXRFutureResult"/> is identical to the return from <see cref="Godot.OpenXRSpatialEntityExtension.DiscoverSpatialEntities(Rid, long[], OpenXRStructureBase, Callable)"/>.</para>
    /// </summary>
    public OpenXRFutureResult StartEntityDiscovery(Rid spatialContext, Godot.Collections.Array<OpenXRSpatialComponentData> componentData, OpenXRStructureBase nextSnapshotCreate = default, OpenXRStructureBase nextSnapshotQuery = default, Callable userCallback = default)
    {
        OpenXRFutureResult ret = (OpenXRFutureResult)NativeCalls.godot_icall_5_986(MethodBind11, GodotObject.GetPtr(this), spatialContext, (godot_array)(componentData ?? new()).NativeValue, GodotObject.GetPtr(nextSnapshotCreate), GodotObject.GetPtr(nextSnapshotQuery), userCallback);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind12 = ClassDB_get_method_with_compatibility(NativeName, MethodName.DoEntityUpdate, 3138044275ul);

    /// <summary>
    /// <para>Calls <see cref="Godot.OpenXRSpatialEntityExtension.UpdateSpatialEntities(Rid, Godot.Collections.Array{Rid}, long[], OpenXRStructureBase)"/> and <see cref="Godot.OpenXRSpatialEntityExtension.QuerySnapshot(Rid, Godot.Collections.Array{OpenXRSpatialComponentData}, OpenXRStructureBase)"/> with the anchor entities associated with <paramref name="spatialContext"/>.</para>
    /// <para><paramref name="componentData"/> are the <see cref="Godot.OpenXRSpatialComponentData"/>s to update for this anchor capability.</para>
    /// <para>If <paramref name="nextSnapshotCreate"/> is non-null, then pass this to the <c>next</c> parameter in <see cref="Godot.OpenXRSpatialEntityExtension.UpdateSpatialEntities(Rid, Godot.Collections.Array{Rid}, long[], OpenXRStructureBase)"/>.</para>
    /// <para>If <paramref name="nextSnapshotQuery"/> is non-null, then pass this to the <c>next</c> parameter in <see cref="Godot.OpenXRSpatialEntityExtension.QuerySnapshot(Rid, Godot.Collections.Array{OpenXRSpatialComponentData}, OpenXRStructureBase)"/>.</para>
    /// </summary>
    public void DoEntityUpdate(Rid spatialContext, Godot.Collections.Array<OpenXRSpatialComponentData> componentData, OpenXRStructureBase nextSnapshotCreate = default, OpenXRStructureBase nextSnapshotQuery = default)
    {
        NativeCalls.godot_icall_4_987(MethodBind12, GodotObject.GetPtr(this), spatialContext, (godot_array)(componentData ?? new()).NativeValue, GodotObject.GetPtr(nextSnapshotCreate), GodotObject.GetPtr(nextSnapshotQuery));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind13 = ClassDB_get_method_with_compatibility(NativeName, MethodName.CreateNewAnchor, 607100373ul);

    /// <summary>
    /// <para>Creates a new anchor that will be tracked by the XR runtime. The <paramref name="transform"/> should be a transform in the local space of your <see cref="Godot.XROrigin3D"/> node. If <paramref name="spatialContext"/> is not specified the default will be used, this requires <c>ProjectSettings.xr/openxr/extensions/spatial_entity/enable_builtin_anchor_detection</c> to be set. The returned tracker will track the location in case our reference space changes.</para>
    /// <para><paramref name="next"/> must be a valid next object for the <c>XrSpatialAnchorCreateInfoEXT</c> chain.</para>
    /// </summary>
    [EditorBrowsable(EditorBrowsableState.Never)]
    public unsafe OpenXRAnchorTracker CreateNewAnchor(Transform3D transform, Rid spatialContext)
    {
        OpenXRAnchorTracker ret = (OpenXRAnchorTracker)NativeCalls.godot_icall_2_988(MethodBind13, GodotObject.GetPtr(this), &transform, spatialContext);
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
    public new class PropertyName : OpenXRExtensionWrapper.PropertyName
    {
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : OpenXRExtensionWrapper.MethodName
    {
        /// <summary>
        /// Cached name for the 'is_spatial_anchor_supported' method.
        /// </summary>
        public static readonly StringName IsSpatialAnchorSupported = "is_spatial_anchor_supported";
        /// <summary>
        /// Cached name for the 'is_spatial_persistence_supported' method.
        /// </summary>
        public static readonly StringName IsSpatialPersistenceSupported = "is_spatial_persistence_supported";
        /// <summary>
        /// Cached name for the 'is_persistence_scope_supported' method.
        /// </summary>
        public static readonly StringName IsPersistenceScopeSupported = "is_persistence_scope_supported";
        /// <summary>
        /// Cached name for the 'create_default_persistence_context' method.
        /// </summary>
        public static readonly StringName CreateDefaultPersistenceContext = "create_default_persistence_context";
        /// <summary>
        /// Cached name for the 'create_persistence_context' method.
        /// </summary>
        public static readonly StringName CreatePersistenceContext = "create_persistence_context";
        /// <summary>
        /// Cached name for the 'get_persistence_context_handle' method.
        /// </summary>
        public static readonly StringName GetPersistenceContextHandle = "get_persistence_context_handle";
        /// <summary>
        /// Cached name for the 'free_persistence_context' method.
        /// </summary>
        public static readonly StringName FreePersistenceContext = "free_persistence_context";
        /// <summary>
        /// Cached name for the 'create_new_anchor' method.
        /// </summary>
        public static readonly StringName CreateNewAnchor = "create_new_anchor";
        /// <summary>
        /// Cached name for the 'remove_anchor' method.
        /// </summary>
        public static readonly StringName RemoveAnchor = "remove_anchor";
        /// <summary>
        /// Cached name for the 'persist_anchor' method.
        /// </summary>
        public static readonly StringName PersistAnchor = "persist_anchor";
        /// <summary>
        /// Cached name for the 'unpersist_anchor' method.
        /// </summary>
        public static readonly StringName UnpersistAnchor = "unpersist_anchor";
        /// <summary>
        /// Cached name for the 'start_entity_discovery' method.
        /// </summary>
        public static readonly StringName StartEntityDiscovery = "start_entity_discovery";
        /// <summary>
        /// Cached name for the 'do_entity_update' method.
        /// </summary>
        public static readonly StringName DoEntityUpdate = "do_entity_update";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : OpenXRExtensionWrapper.SignalName
    {
    }
}
