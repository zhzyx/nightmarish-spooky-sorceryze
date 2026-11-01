namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>This class handles the OpenXR marker tracking spatial entity extension.</para>
/// </summary>
public partial class OpenXRSpatialMarkerTrackingCapability : OpenXRExtensionWrapper
{
    [System.Flags]
    public enum MarkerTypeFlags : long
    {
        /// <summary>
        /// <para>QR Code.</para>
        /// </summary>
        QrCode = 1,
        /// <summary>
        /// <para>Micro QR Code.</para>
        /// </summary>
        MicroQrCode = 2,
        /// <summary>
        /// <para>ArUco marker.</para>
        /// </summary>
        Aruco = 4,
        /// <summary>
        /// <para>April tag.</para>
        /// </summary>
        AprilTag = 8
    }

    private static readonly System.Type CachedType = typeof(OpenXRSpatialMarkerTrackingCapability);

    private static readonly StringName NativeName = "OpenXRSpatialMarkerTrackingCapability";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public OpenXRSpatialMarkerTrackingCapability() : this(false)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: false);
        }
    }

    internal OpenXRSpatialMarkerTrackingCapability(IntPtr ptr) : this(false)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal OpenXRSpatialMarkerTrackingCapability(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsQrcodeSupported, 2240911060ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if QR code marker tracking is supported by the current device.</para>
    /// </summary>
    public bool IsQrcodeSupported()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind0, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsMicroQrcodeSupported, 2240911060ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if micro QR code marker tracking is supported by the current device.</para>
    /// </summary>
    public bool IsMicroQrcodeSupported()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind1, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsArucoSupported, 2240911060ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if ArUco marker tracking is supported by the current device.</para>
    /// </summary>
    public bool IsArucoSupported()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind2, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsAprilTagSupported, 2240911060ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if April tag marker tracking is supported by the current device.</para>
    /// </summary>
    public bool IsAprilTagSupported()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind3, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.StartEntityDiscovery, 3452714169ul);

    /// <summary>
    /// <para>Calls <see cref="Godot.OpenXRSpatialEntityExtension.DiscoverSpatialEntities(Rid, long[], OpenXRStructureBase, Callable)"/> and <see cref="Godot.OpenXRSpatialEntityExtension.QuerySnapshot(Rid, Godot.Collections.Array{OpenXRSpatialComponentData}, OpenXRStructureBase)"/> with the marker entities associated with <paramref name="spatialContext"/>.</para>
    /// <para><paramref name="componentData"/> are the <see cref="Godot.OpenXRSpatialComponentData"/>s to discover for this marker capability.</para>
    /// <para>If <paramref name="nextSnapshotCreate"/> is non-null, then pass this to the <c>next</c> parameter in <see cref="Godot.OpenXRSpatialEntityExtension.DiscoverSpatialEntities(Rid, long[], OpenXRStructureBase, Callable)"/>.</para>
    /// <para>If <paramref name="nextSnapshotQuery"/> is non-null, then pass this to the <c>next</c> parameter in <see cref="Godot.OpenXRSpatialEntityExtension.QuerySnapshot(Rid, Godot.Collections.Array{OpenXRSpatialComponentData}, OpenXRStructureBase)"/>.</para>
    /// <para><paramref name="userCallback"/>, when non-null, is called with two parameters usually twice. The first parameter is the <see cref="Godot.Rid"/> of the discovery snapshot and the second parameter is a boolean where <see langword="false"/> indicates the discovery snapshot is about to be processed, and <see langword="true"/> indicates the discovery snapshot has been processed and <paramref name="componentData"/> has valid data. The second call is skipped if an error was encountered.</para>
    /// <para>The returned <see cref="Godot.OpenXRFutureResult"/> is identical to the return from <see cref="Godot.OpenXRSpatialEntityExtension.DiscoverSpatialEntities(Rid, long[], OpenXRStructureBase, Callable)"/>.</para>
    /// </summary>
    public OpenXRFutureResult StartEntityDiscovery(Rid spatialContext, Godot.Collections.Array<OpenXRSpatialComponentData> componentData, OpenXRStructureBase nextSnapshotCreate = default, OpenXRStructureBase nextSnapshotQuery = default, Callable userCallback = default)
    {
        OpenXRFutureResult ret = (OpenXRFutureResult)NativeCalls.godot_icall_5_986(MethodBind4, GodotObject.GetPtr(this), spatialContext, (godot_array)(componentData ?? new()).NativeValue, GodotObject.GetPtr(nextSnapshotCreate), GodotObject.GetPtr(nextSnapshotQuery), userCallback);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.DoEntityUpdate, 3138044275ul);

    /// <summary>
    /// <para>Calls <see cref="Godot.OpenXRSpatialEntityExtension.UpdateSpatialEntities(Rid, Godot.Collections.Array{Rid}, long[], OpenXRStructureBase)"/> and <see cref="Godot.OpenXRSpatialEntityExtension.QuerySnapshot(Rid, Godot.Collections.Array{OpenXRSpatialComponentData}, OpenXRStructureBase)"/> with the marker entities associated with <paramref name="spatialContext"/>.</para>
    /// <para><paramref name="componentData"/> are the <see cref="Godot.OpenXRSpatialComponentData"/>s to update for this marker capability.</para>
    /// <para>If <paramref name="nextSnapshotCreate"/> is non-null, then pass this to the <c>next</c> parameter in <see cref="Godot.OpenXRSpatialEntityExtension.UpdateSpatialEntities(Rid, Godot.Collections.Array{Rid}, long[], OpenXRStructureBase)"/>.</para>
    /// <para>If <paramref name="nextSnapshotQuery"/> is non-null, then pass this to the <c>next</c> parameter in <see cref="Godot.OpenXRSpatialEntityExtension.QuerySnapshot(Rid, Godot.Collections.Array{OpenXRSpatialComponentData}, OpenXRStructureBase)"/>.</para>
    /// </summary>
    public void DoEntityUpdate(Rid spatialContext, Godot.Collections.Array<OpenXRSpatialComponentData> componentData, OpenXRStructureBase nextSnapshotCreate = default, OpenXRStructureBase nextSnapshotQuery = default)
    {
        NativeCalls.godot_icall_4_987(MethodBind5, GodotObject.GetPtr(this), spatialContext, (godot_array)(componentData ?? new()).NativeValue, GodotObject.GetPtr(nextSnapshotCreate), GodotObject.GetPtr(nextSnapshotQuery));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetBuiltInTrackingState, 434811308ul);

    /// <summary>
    /// <para>Returns the state of the built-in tracking system.</para>
    /// </summary>
    public OpenXRSpatialEntityExtension.TrackingState GetBuiltInTrackingState()
    {
        OpenXRSpatialEntityExtension.TrackingState ret = (OpenXRSpatialEntityExtension.TrackingState)NativeCalls.godot_icall_0_39(MethodBind6, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.StartBuiltInTracking, 4090240782ul);

    /// <summary>
    /// <para>Starts the built-in marker tracking logic for the specified marker types. This will fail if built-in tracking is already enabled.</para>
    /// </summary>
    public bool StartBuiltInTracking(OpenXRSpatialMarkerTrackingCapability.MarkerTypeFlags markerTypes)
    {
        bool ret = NativeCalls.godot_icall_1_86(MethodBind7, GodotObject.GetPtr(this), (int)markerTypes).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = ClassDB_get_method_with_compatibility(NativeName, MethodName.StopBuiltInTracking, 3216645846ul);

    /// <summary>
    /// <para>Stops the built-in marker tracking logic.</para>
    /// </summary>
    public void StopBuiltInTracking(bool clearTrackers = true)
    {
        NativeCalls.godot_icall_1_14(MethodBind8, GodotObject.GetPtr(this), clearTrackers.ToGodotBool());
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
    public new class PropertyName : OpenXRExtensionWrapper.PropertyName
    {
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : OpenXRExtensionWrapper.MethodName
    {
        /// <summary>
        /// Cached name for the 'is_qrcode_supported' method.
        /// </summary>
        public static readonly StringName IsQrcodeSupported = "is_qrcode_supported";
        /// <summary>
        /// Cached name for the 'is_micro_qrcode_supported' method.
        /// </summary>
        public static readonly StringName IsMicroQrcodeSupported = "is_micro_qrcode_supported";
        /// <summary>
        /// Cached name for the 'is_aruco_supported' method.
        /// </summary>
        public static readonly StringName IsArucoSupported = "is_aruco_supported";
        /// <summary>
        /// Cached name for the 'is_april_tag_supported' method.
        /// </summary>
        public static readonly StringName IsAprilTagSupported = "is_april_tag_supported";
        /// <summary>
        /// Cached name for the 'start_entity_discovery' method.
        /// </summary>
        public static readonly StringName StartEntityDiscovery = "start_entity_discovery";
        /// <summary>
        /// Cached name for the 'do_entity_update' method.
        /// </summary>
        public static readonly StringName DoEntityUpdate = "do_entity_update";
        /// <summary>
        /// Cached name for the 'get_built_in_tracking_state' method.
        /// </summary>
        public static readonly StringName GetBuiltInTrackingState = "get_built_in_tracking_state";
        /// <summary>
        /// Cached name for the 'start_built_in_tracking' method.
        /// </summary>
        public static readonly StringName StartBuiltInTracking = "start_built_in_tracking";
        /// <summary>
        /// Cached name for the 'stop_built_in_tracking' method.
        /// </summary>
        public static readonly StringName StopBuiltInTracking = "stop_built_in_tracking";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : OpenXRExtensionWrapper.SignalName
    {
    }
}
