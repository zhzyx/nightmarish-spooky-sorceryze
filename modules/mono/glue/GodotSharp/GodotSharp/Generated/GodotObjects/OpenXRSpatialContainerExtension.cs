namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>OpenXR extension that handles spatial containers. Enabling this extension will automatically create a main spatial container, and update the lifecycle of the XR application.</para>
/// </summary>
public partial class OpenXRSpatialContainerExtension : OpenXRExtensionWrapper
{
    private static readonly System.Type CachedType = typeof(OpenXRSpatialContainerExtension);

    private static readonly StringName NativeName = "OpenXRSpatialContainerExtension";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public OpenXRSpatialContainerExtension() : this(false)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: false);
        }
    }

    internal OpenXRSpatialContainerExtension(IntPtr ptr) : this(false)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal OpenXRSpatialContainerExtension(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsEnabled, 36873697ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if spatial containers are enabled in the project settings and available on the current runtime.</para>
    /// </summary>
    public bool IsEnabled()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind0, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsSpatialContainerActive, 36873697ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if the main spatial container is active.</para>
    /// </summary>
    public bool IsSpatialContainerActive()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind1, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetSupportedBoundsModes, 2915620761ul);

    /// <summary>
    /// <para>Returns an array of supported spatial container bounds mode, see <see cref="Godot.OpenXRSpatialContainerState.BoundsMode"/>.</para>
    /// </summary>
    public Godot.Collections.Array GetSupportedBoundsModes()
    {
        Godot.Collections.Array ret = NativeCalls.godot_icall_0_146(MethodBind2, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetSpatialContainerState, 212870561ul);

    /// <summary>
    /// <para>Retrieves the <see cref="Godot.OpenXRSpatialContainerState"/> of the main spatial container.</para>
    /// </summary>
    public OpenXRSpatialContainerState GetSpatialContainerState()
    {
        OpenXRSpatialContainerState ret = (OpenXRSpatialContainerState)NativeCalls.godot_icall_0_87(MethodBind3, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetSpatialContainerBounds, 3783033775ul);

    /// <summary>
    /// <para>Retrieves the bounds of the main spatial container.</para>
    /// </summary>
    public Vector3 GetSpatialContainerBounds()
    {
        Vector3 ret = NativeCalls.godot_icall_0_151(MethodBind4, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.RequestSpatialContainerBoundsMode, 1261129373ul);

    /// <summary>
    /// <para>Sends a request to the runtime to update the bounds mode of the main spatial container.</para>
    /// <para>If the request is accepted, <see cref="Godot.OpenXRSpatialContainerExtension.SpatialContainerBoundsChanged"/> will be emitted with the updated bounds mode.</para>
    /// <para>Otherwise, <see cref="Godot.OpenXRSpatialContainerExtension.SpatialContainerBoundsModeRequestDenied"/> will be emitted.</para>
    /// </summary>
    public bool RequestSpatialContainerBoundsMode(OpenXRSpatialContainerState.BoundsMode boundsMode)
    {
        bool ret = NativeCalls.godot_icall_1_86(MethodBind5, GodotObject.GetPtr(this), (int)boundsMode).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.RequestSpatialContainerVisible, 2703660260ul);

    /// <summary>
    /// <para>Sends a request to the runtime to update the visibility of the spatial container.</para>
    /// <para>If the request is accepted, <see cref="Godot.OpenXRSpatialContainerExtension.SpatialContainerVisibleChanged"/> will be emitted with the updated visibility.</para>
    /// <para>Otherwise, <see cref="Godot.OpenXRSpatialContainerExtension.SpatialContainerVisibleRequestDenied"/> will be emitted.</para>
    /// </summary>
    public bool RequestSpatialContainerVisible(bool visible)
    {
        bool ret = NativeCalls.godot_icall_1_364(MethodBind6, GodotObject.GetPtr(this), visible.ToGodotBool()).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.OpenXRSpatialContainerExtension.SpatialContainerBoundsChanged"/> event of a <see cref="Godot.OpenXRSpatialContainerExtension"/> class.
    /// </summary>
    public delegate void SpatialContainerBoundsChangedEventHandler(Rid spatialContainerRid, bool spatialContainerInfiniteBounds, long spatialContainerBoundsMode, Vector3 spatialContainerBounds);

    private static void SpatialContainerBoundsChangedTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 4);
        ((SpatialContainerBoundsChangedEventHandler)delegateObj)(VariantUtils.ConvertTo<Rid>(args[0]), VariantUtils.ConvertTo<bool>(args[1]), VariantUtils.ConvertTo<long>(args[2]), VariantUtils.ConvertTo<Vector3>(args[3]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted when the bounds of the spatial container specified by <c>spatialContainerRid</c> are updated.</para>
    /// </summary>
    public unsafe event SpatialContainerBoundsChangedEventHandler SpatialContainerBoundsChanged
    {
        add => Connect(SignalName.SpatialContainerBoundsChanged, Callable.CreateWithUnsafeTrampoline(value, &SpatialContainerBoundsChangedTrampoline));
        remove => Disconnect(SignalName.SpatialContainerBoundsChanged, Callable.CreateWithUnsafeTrampoline(value, &SpatialContainerBoundsChangedTrampoline));
    }

    protected void EmitSignalSpatialContainerBoundsChanged(Rid spatialContainerRid, bool spatialContainerInfiniteBounds, long spatialContainerBoundsMode, Vector3 spatialContainerBounds)
    {
        EmitSignal(SignalName.SpatialContainerBoundsChanged, spatialContainerRid, spatialContainerInfiniteBounds, spatialContainerBoundsMode, spatialContainerBounds);
    }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.OpenXRSpatialContainerExtension.SpatialContainerBoundsModeRequestDenied"/> event of a <see cref="Godot.OpenXRSpatialContainerExtension"/> class.
    /// </summary>
    public delegate void SpatialContainerBoundsModeRequestDeniedEventHandler(Rid spatialContainerRid);

    private static void SpatialContainerBoundsModeRequestDeniedTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 1);
        ((SpatialContainerBoundsModeRequestDeniedEventHandler)delegateObj)(VariantUtils.ConvertTo<Rid>(args[0]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted when a request to update the bounds mode of the spatial container specified by <c>spatialContainerRid</c> is denied by the runtime.</para>
    /// </summary>
    public unsafe event SpatialContainerBoundsModeRequestDeniedEventHandler SpatialContainerBoundsModeRequestDenied
    {
        add => Connect(SignalName.SpatialContainerBoundsModeRequestDenied, Callable.CreateWithUnsafeTrampoline(value, &SpatialContainerBoundsModeRequestDeniedTrampoline));
        remove => Disconnect(SignalName.SpatialContainerBoundsModeRequestDenied, Callable.CreateWithUnsafeTrampoline(value, &SpatialContainerBoundsModeRequestDeniedTrampoline));
    }

    protected void EmitSignalSpatialContainerBoundsModeRequestDenied(Rid spatialContainerRid)
    {
        EmitSignal(SignalName.SpatialContainerBoundsModeRequestDenied, spatialContainerRid);
    }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.OpenXRSpatialContainerExtension.SpatialContainerClosed"/> event of a <see cref="Godot.OpenXRSpatialContainerExtension"/> class.
    /// </summary>
    public delegate void SpatialContainerClosedEventHandler(Rid spatialContainerRid);

    private static void SpatialContainerClosedTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 1);
        ((SpatialContainerClosedEventHandler)delegateObj)(VariantUtils.ConvertTo<Rid>(args[0]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted when the spatial container specified by <c>spatialContainerRid</c> is closed.</para>
    /// </summary>
    public unsafe event SpatialContainerClosedEventHandler SpatialContainerClosed
    {
        add => Connect(SignalName.SpatialContainerClosed, Callable.CreateWithUnsafeTrampoline(value, &SpatialContainerClosedTrampoline));
        remove => Disconnect(SignalName.SpatialContainerClosed, Callable.CreateWithUnsafeTrampoline(value, &SpatialContainerClosedTrampoline));
    }

    protected void EmitSignalSpatialContainerClosed(Rid spatialContainerRid)
    {
        EmitSignal(SignalName.SpatialContainerClosed, spatialContainerRid);
    }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.OpenXRSpatialContainerExtension.SpatialContainerInteractableChanged"/> event of a <see cref="Godot.OpenXRSpatialContainerExtension"/> class.
    /// </summary>
    public delegate void SpatialContainerInteractableChangedEventHandler(Rid spatialContainerRid, bool spatialContainerInteractable);

    private static void SpatialContainerInteractableChangedTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 2);
        ((SpatialContainerInteractableChangedEventHandler)delegateObj)(VariantUtils.ConvertTo<Rid>(args[0]), VariantUtils.ConvertTo<bool>(args[1]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted when the interactability of the spatial container specified by <c>spatialContainerRid</c> is updated.</para>
    /// </summary>
    public unsafe event SpatialContainerInteractableChangedEventHandler SpatialContainerInteractableChanged
    {
        add => Connect(SignalName.SpatialContainerInteractableChanged, Callable.CreateWithUnsafeTrampoline(value, &SpatialContainerInteractableChangedTrampoline));
        remove => Disconnect(SignalName.SpatialContainerInteractableChanged, Callable.CreateWithUnsafeTrampoline(value, &SpatialContainerInteractableChangedTrampoline));
    }

    protected void EmitSignalSpatialContainerInteractableChanged(Rid spatialContainerRid, bool spatialContainerInteractable)
    {
        EmitSignal(SignalName.SpatialContainerInteractableChanged, spatialContainerRid, spatialContainerInteractable);
    }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.OpenXRSpatialContainerExtension.SpatialContainerVisibleChanged"/> event of a <see cref="Godot.OpenXRSpatialContainerExtension"/> class.
    /// </summary>
    public delegate void SpatialContainerVisibleChangedEventHandler(Rid spatialContainerRid, bool spatialContainerVisible);

    private static void SpatialContainerVisibleChangedTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 2);
        ((SpatialContainerVisibleChangedEventHandler)delegateObj)(VariantUtils.ConvertTo<Rid>(args[0]), VariantUtils.ConvertTo<bool>(args[1]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted when the visibility of the spatial container specified by <c>spatialContainerRid</c> is updated.</para>
    /// </summary>
    public unsafe event SpatialContainerVisibleChangedEventHandler SpatialContainerVisibleChanged
    {
        add => Connect(SignalName.SpatialContainerVisibleChanged, Callable.CreateWithUnsafeTrampoline(value, &SpatialContainerVisibleChangedTrampoline));
        remove => Disconnect(SignalName.SpatialContainerVisibleChanged, Callable.CreateWithUnsafeTrampoline(value, &SpatialContainerVisibleChangedTrampoline));
    }

    protected void EmitSignalSpatialContainerVisibleChanged(Rid spatialContainerRid, bool spatialContainerVisible)
    {
        EmitSignal(SignalName.SpatialContainerVisibleChanged, spatialContainerRid, spatialContainerVisible);
    }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.OpenXRSpatialContainerExtension.SpatialContainerVisibleRequestDenied"/> event of a <see cref="Godot.OpenXRSpatialContainerExtension"/> class.
    /// </summary>
    public delegate void SpatialContainerVisibleRequestDeniedEventHandler(Rid spatialContainerRid);

    private static void SpatialContainerVisibleRequestDeniedTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 1);
        ((SpatialContainerVisibleRequestDeniedEventHandler)delegateObj)(VariantUtils.ConvertTo<Rid>(args[0]));
        ret = default;
    }

    /// <summary>
    /// <para>Emitted when the runtime denies the visibility request of the spatial container specified by <c>spatialContainerRid</c>.</para>
    /// </summary>
    public unsafe event SpatialContainerVisibleRequestDeniedEventHandler SpatialContainerVisibleRequestDenied
    {
        add => Connect(SignalName.SpatialContainerVisibleRequestDenied, Callable.CreateWithUnsafeTrampoline(value, &SpatialContainerVisibleRequestDeniedTrampoline));
        remove => Disconnect(SignalName.SpatialContainerVisibleRequestDenied, Callable.CreateWithUnsafeTrampoline(value, &SpatialContainerVisibleRequestDeniedTrampoline));
    }

    protected void EmitSignalSpatialContainerVisibleRequestDenied(Rid spatialContainerRid)
    {
        EmitSignal(SignalName.SpatialContainerVisibleRequestDenied, spatialContainerRid);
    }

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_spatial_container_bounds_changed = "SpatialContainerBoundsChanged";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_spatial_container_bounds_mode_request_denied = "SpatialContainerBoundsModeRequestDenied";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_spatial_container_closed = "SpatialContainerClosed";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_spatial_container_interactable_changed = "SpatialContainerInteractableChanged";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_spatial_container_visible_changed = "SpatialContainerVisibleChanged";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_spatial_container_visible_request_denied = "SpatialContainerVisibleRequestDenied";

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
        if (signal == SignalName.SpatialContainerBoundsChanged)
        {
            if (HasGodotClassSignal(SignalProxyName_spatial_container_bounds_changed.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.SpatialContainerBoundsModeRequestDenied)
        {
            if (HasGodotClassSignal(SignalProxyName_spatial_container_bounds_mode_request_denied.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.SpatialContainerClosed)
        {
            if (HasGodotClassSignal(SignalProxyName_spatial_container_closed.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.SpatialContainerInteractableChanged)
        {
            if (HasGodotClassSignal(SignalProxyName_spatial_container_interactable_changed.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.SpatialContainerVisibleChanged)
        {
            if (HasGodotClassSignal(SignalProxyName_spatial_container_visible_changed.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.SpatialContainerVisibleRequestDenied)
        {
            if (HasGodotClassSignal(SignalProxyName_spatial_container_visible_request_denied.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
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
        /// Cached name for the 'is_enabled' method.
        /// </summary>
        public static readonly StringName IsEnabled = "is_enabled";
        /// <summary>
        /// Cached name for the 'is_spatial_container_active' method.
        /// </summary>
        public static readonly StringName IsSpatialContainerActive = "is_spatial_container_active";
        /// <summary>
        /// Cached name for the 'get_supported_bounds_modes' method.
        /// </summary>
        public static readonly StringName GetSupportedBoundsModes = "get_supported_bounds_modes";
        /// <summary>
        /// Cached name for the 'get_spatial_container_state' method.
        /// </summary>
        public static readonly StringName GetSpatialContainerState = "get_spatial_container_state";
        /// <summary>
        /// Cached name for the 'get_spatial_container_bounds' method.
        /// </summary>
        public static readonly StringName GetSpatialContainerBounds = "get_spatial_container_bounds";
        /// <summary>
        /// Cached name for the 'request_spatial_container_bounds_mode' method.
        /// </summary>
        public static readonly StringName RequestSpatialContainerBoundsMode = "request_spatial_container_bounds_mode";
        /// <summary>
        /// Cached name for the 'request_spatial_container_visible' method.
        /// </summary>
        public static readonly StringName RequestSpatialContainerVisible = "request_spatial_container_visible";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : OpenXRExtensionWrapper.SignalName
    {
        /// <summary>
        /// Cached name for the 'spatial_container_bounds_changed' signal.
        /// </summary>
        public static readonly StringName SpatialContainerBoundsChanged = "spatial_container_bounds_changed";
        /// <summary>
        /// Cached name for the 'spatial_container_bounds_mode_request_denied' signal.
        /// </summary>
        public static readonly StringName SpatialContainerBoundsModeRequestDenied = "spatial_container_bounds_mode_request_denied";
        /// <summary>
        /// Cached name for the 'spatial_container_closed' signal.
        /// </summary>
        public static readonly StringName SpatialContainerClosed = "spatial_container_closed";
        /// <summary>
        /// Cached name for the 'spatial_container_interactable_changed' signal.
        /// </summary>
        public static readonly StringName SpatialContainerInteractableChanged = "spatial_container_interactable_changed";
        /// <summary>
        /// Cached name for the 'spatial_container_visible_changed' signal.
        /// </summary>
        public static readonly StringName SpatialContainerVisibleChanged = "spatial_container_visible_changed";
        /// <summary>
        /// Cached name for the 'spatial_container_visible_request_denied' signal.
        /// </summary>
        public static readonly StringName SpatialContainerVisibleRequestDenied = "spatial_container_visible_request_denied";
    }
}
