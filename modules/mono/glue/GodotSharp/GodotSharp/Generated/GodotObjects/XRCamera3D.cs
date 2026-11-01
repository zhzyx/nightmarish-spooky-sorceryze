namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>A camera node which automatically positions itself based on XR tracking data.</para>
/// <para><b>Note:</b> Due to the nature of headsets, camera positioning needs to update every frame even when your game is paused. <see cref="Godot.Node.ProcessMode"/> must be set to <see cref="Godot.Node.ProcessModeEnum.Always"/>.</para>
/// </summary>
public partial class XRCamera3D : Camera3D
{
    /// <summary>
    /// <para>The name of the camera tracker we're bound to. Which trackers are available is not known during design time.</para>
    /// <para>The default tracker refers to the HMD position of the main player. Consult the documentation of the <see cref="Godot.XRInterface"/> for any additional trackers. There may be additional tracked headsets for multiplayer systems or a tracker may be available for a physical camera in a mixed reality scenario.</para>
    /// </summary>
    public StringName Tracker
    {
        get
        {
            return GetTracker();
        }
        set
        {
            SetTracker(value);
        }
    }

    private static readonly System.Type CachedType = typeof(XRCamera3D);

    private static readonly StringName NativeName = "XRCamera3D";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public XRCamera3D() : this(false)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: false);
        }
    }

    internal XRCamera3D(IntPtr ptr) : this(false)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal XRCamera3D(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetTracker, 3304788590ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetTracker(StringName trackerName)
    {
        NativeCalls.godot_icall_1_88(MethodBind0, GodotObject.GetPtr(this), (godot_string_name)(trackerName?.NativeValue ?? default));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetTracker, 2002593661ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public StringName GetTracker()
    {
        StringName ret = NativeCalls.godot_icall_0_89(MethodBind1, GodotObject.GetPtr(this));
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
    public new class PropertyName : Camera3D.PropertyName
    {
        /// <summary>
        /// Cached name for the 'tracker' property.
        /// </summary>
        public static readonly StringName Tracker = "tracker";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : Camera3D.MethodName
    {
        /// <summary>
        /// Cached name for the 'set_tracker' method.
        /// </summary>
        public static readonly StringName SetTracker = "set_tracker";
        /// <summary>
        /// Cached name for the 'get_tracker' method.
        /// </summary>
        public static readonly StringName GetTracker = "get_tracker";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : Camera3D.SignalName
    {
    }
}
