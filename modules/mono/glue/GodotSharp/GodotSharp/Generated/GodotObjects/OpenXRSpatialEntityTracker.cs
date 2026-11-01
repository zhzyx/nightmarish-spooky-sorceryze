namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>These are trackers created and managed by OpenXR's spatial entity extensions that give access to specific data related to OpenXR's spatial entities. They will always be of type <c>TRACKER_ANCHOR</c>.</para>
/// </summary>
public partial class OpenXRSpatialEntityTracker : XRPositionalTracker
{
    public enum EntityTrackingState : long
    {
        /// <summary>
        /// <para>This anchor has stopped tracking.</para>
        /// </summary>
        Stopped = 1,
        /// <summary>
        /// <para>Tracking is currently paused.</para>
        /// </summary>
        Paused = 2,
        /// <summary>
        /// <para>This anchor is currently being tracked.</para>
        /// </summary>
        Tracking = 3
    }

    /// <summary>
    /// <para>The spatial entity associated with this tracker.</para>
    /// </summary>
    public Rid Entity
    {
        get
        {
            return GetEntity();
        }
        set
        {
            SetEntity(value);
        }
    }

    /// <summary>
    /// <para>The spatial tracking state for this tracker.</para>
    /// </summary>
    public OpenXRSpatialEntityTracker.EntityTrackingState SpatialTrackingState
    {
        get
        {
            return GetSpatialTrackingState();
        }
        set
        {
            SetSpatialTrackingState(value);
        }
    }

    private static readonly System.Type CachedType = typeof(OpenXRSpatialEntityTracker);

    private static readonly StringName NativeName = "OpenXRSpatialEntityTracker";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public OpenXRSpatialEntityTracker() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal OpenXRSpatialEntityTracker(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal OpenXRSpatialEntityTracker(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetSpatialContext, 2722037293ul);

    /// <summary>
    /// <para>Sets the spatial context used to create this tracker.</para>
    /// </summary>
    public void SetSpatialContext(Rid spatialContext)
    {
        NativeCalls.godot_icall_1_63(MethodBind0, GodotObject.GetPtr(this), spatialContext);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetSpatialContext, 2944877500ul);

    /// <summary>
    /// <para>Gets the spatial context used to create this <see cref="Godot.OpenXRSpatialEntityTracker"/>.</para>
    /// </summary>
    public Rid GetSpatialContext()
    {
        Rid ret = NativeCalls.godot_icall_0_267(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetEntity, 2722037293ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetEntity(Rid entity)
    {
        NativeCalls.godot_icall_1_63(MethodBind2, GodotObject.GetPtr(this), entity);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetEntity, 2944877500ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Rid GetEntity()
    {
        Rid ret = NativeCalls.godot_icall_0_267(MethodBind3, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetSpatialTrackingState, 2170234447ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetSpatialTrackingState(OpenXRSpatialEntityTracker.EntityTrackingState spatialTrackingState)
    {
        NativeCalls.godot_icall_1_38(MethodBind4, GodotObject.GetPtr(this), (int)spatialTrackingState);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetSpatialTrackingState, 3351876560ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public OpenXRSpatialEntityTracker.EntityTrackingState GetSpatialTrackingState()
    {
        OpenXRSpatialEntityTracker.EntityTrackingState ret = (OpenXRSpatialEntityTracker.EntityTrackingState)NativeCalls.godot_icall_0_39(MethodBind5, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetNext, 2798796760ul);

    /// <summary>
    /// <para>Gets the head <see cref="Godot.OpenXRStructureBase"/> in the next-chain.</para>
    /// <para>See also <see cref="Godot.OpenXRSpatialEntityTracker.AddNext(OpenXRStructureBase)"/> and <see cref="Godot.OpenXRSpatialEntityTracker.RemoveNext(OpenXRStructureBase)"/>.</para>
    /// </summary>
    public OpenXRStructureBase GetNext()
    {
        OpenXRStructureBase ret = (OpenXRStructureBase)NativeCalls.godot_icall_0_87(MethodBind6, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.AddNext, 334698771ul);

    /// <summary>
    /// <para>Adds a new <see cref="Godot.OpenXRStructureBase"/> to the next-chain.</para>
    /// <para><see cref="Godot.OpenXRSpatialEntityTracker.GetNext()"/> will return this <paramref name="next"/> until either <see cref="Godot.OpenXRSpatialEntityTracker.AddNext(OpenXRStructureBase)"/> is called again or it's removed in <see cref="Godot.OpenXRSpatialEntityTracker.RemoveNext(OpenXRStructureBase)"/>.</para>
    /// </summary>
    public void AddNext(OpenXRStructureBase next)
    {
        NativeCalls.godot_icall_1_56(MethodBind7, GodotObject.GetPtr(this), GodotObject.GetPtr(next));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = ClassDB_get_method_with_compatibility(NativeName, MethodName.RemoveNext, 334698771ul);

    /// <summary>
    /// <para>Removes a <paramref name="next"/> object previously added in <see cref="Godot.OpenXRSpatialEntityTracker.AddNext(OpenXRStructureBase)"/> from the next-chain.</para>
    /// </summary>
    public void RemoveNext(OpenXRStructureBase next)
    {
        NativeCalls.godot_icall_1_56(MethodBind8, GodotObject.GetPtr(this), GodotObject.GetPtr(next));
        global::System.GC.KeepAlive(this);
    }

    /// <summary>
    /// <para>Emitted when the next-chain changes, from either <see cref="Godot.OpenXRSpatialEntityTracker.AddNext(OpenXRStructureBase)"/> or <see cref="Godot.OpenXRSpatialEntityTracker.RemoveNext(OpenXRStructureBase)"/>.</para>
    /// </summary>
    public event Action NextChanged
    {
        add => Connect(SignalName.NextChanged, Callable.From(value));
        remove => Disconnect(SignalName.NextChanged, Callable.From(value));
    }

    protected void EmitSignalNextChanged()
    {
        EmitSignal(SignalName.NextChanged);
    }

    /// <summary>
    /// Represents the method that handles the <see cref="Godot.OpenXRSpatialEntityTracker.SpatialTrackingStateChanged"/> event of a <see cref="Godot.OpenXRSpatialEntityTracker"/> class.
    /// </summary>
    public delegate void SpatialTrackingStateChangedEventHandler(long spatialTrackingState);

    private static void SpatialTrackingStateChangedTrampoline(object delegateObj, NativeVariantPtrArgs args, out godot_variant ret)
    {
        Callable.ThrowIfArgCountMismatch(args, 1);
        ((SpatialTrackingStateChangedEventHandler)delegateObj)(VariantUtils.ConvertTo<long>(args[0]));
        ret = default;
    }

    public unsafe event SpatialTrackingStateChangedEventHandler SpatialTrackingStateChanged
    {
        add => Connect(SignalName.SpatialTrackingStateChanged, Callable.CreateWithUnsafeTrampoline(value, &SpatialTrackingStateChangedTrampoline));
        remove => Disconnect(SignalName.SpatialTrackingStateChanged, Callable.CreateWithUnsafeTrampoline(value, &SpatialTrackingStateChangedTrampoline));
    }

    protected void EmitSignalSpatialTrackingStateChanged(long spatialTrackingState)
    {
        EmitSignal(SignalName.SpatialTrackingStateChanged, spatialTrackingState);
    }

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_next_changed = "NextChanged";

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_spatial_tracking_state_changed = "SpatialTrackingStateChanged";

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
        if (signal == SignalName.NextChanged)
        {
            if (HasGodotClassSignal(SignalProxyName_next_changed.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        if (signal == SignalName.SpatialTrackingStateChanged)
        {
            if (HasGodotClassSignal(SignalProxyName_spatial_tracking_state_changed.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        return base.HasGodotClassSignal(signal);
    }

    /// <summary>
    /// Cached StringNames for the properties and fields contained in this class, for fast lookup.
    /// </summary>
    public new class PropertyName : XRPositionalTracker.PropertyName
    {
        /// <summary>
        /// Cached name for the 'entity' property.
        /// </summary>
        public static readonly StringName Entity = "entity";
        /// <summary>
        /// Cached name for the 'spatial_tracking_state' property.
        /// </summary>
        public static readonly StringName SpatialTrackingState = "spatial_tracking_state";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : XRPositionalTracker.MethodName
    {
        /// <summary>
        /// Cached name for the 'set_spatial_context' method.
        /// </summary>
        public static readonly StringName SetSpatialContext = "set_spatial_context";
        /// <summary>
        /// Cached name for the 'get_spatial_context' method.
        /// </summary>
        public static readonly StringName GetSpatialContext = "get_spatial_context";
        /// <summary>
        /// Cached name for the 'set_entity' method.
        /// </summary>
        public static readonly StringName SetEntity = "set_entity";
        /// <summary>
        /// Cached name for the 'get_entity' method.
        /// </summary>
        public static readonly StringName GetEntity = "get_entity";
        /// <summary>
        /// Cached name for the 'set_spatial_tracking_state' method.
        /// </summary>
        public static readonly StringName SetSpatialTrackingState = "set_spatial_tracking_state";
        /// <summary>
        /// Cached name for the 'get_spatial_tracking_state' method.
        /// </summary>
        public static readonly StringName GetSpatialTrackingState = "get_spatial_tracking_state";
        /// <summary>
        /// Cached name for the 'get_next' method.
        /// </summary>
        public static readonly StringName GetNext = "get_next";
        /// <summary>
        /// Cached name for the 'add_next' method.
        /// </summary>
        public static readonly StringName AddNext = "add_next";
        /// <summary>
        /// Cached name for the 'remove_next' method.
        /// </summary>
        public static readonly StringName RemoveNext = "remove_next";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : XRPositionalTracker.SignalName
    {
        /// <summary>
        /// Cached name for the 'next_changed' signal.
        /// </summary>
        public static readonly StringName NextChanged = "next_changed";
        /// <summary>
        /// Cached name for the 'spatial_tracking_state_changed' signal.
        /// </summary>
        public static readonly StringName SpatialTrackingStateChanged = "spatial_tracking_state_changed";
    }
}
