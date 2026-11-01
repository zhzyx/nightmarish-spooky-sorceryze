namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>This viewport is used for rendering our foveated inset. When foveated inset rendering is supported OpenXR will create and configure this viewport correctly and use its output. The viewport will be available after OpenXR reaches the "begun" state. You can access it by calling <c>get_tree().get_root().get_node("OpenXRFoveatedInsetViewport")</c> at this time.</para>
/// </summary>
public partial class OpenXRFoveatedInsetViewport : SubViewport
{
    private static readonly System.Type CachedType = typeof(OpenXRFoveatedInsetViewport);

    private static readonly StringName NativeName = "OpenXRFoveatedInsetViewport";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public OpenXRFoveatedInsetViewport() : this(false)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: false);
        }
    }

    internal OpenXRFoveatedInsetViewport(IntPtr ptr) : this(false)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal OpenXRFoveatedInsetViewport(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetXROrigin3D, 505038244ul);

    /// <summary>
    /// <para>Returns the <see cref="Godot.XROrigin3D"/> node used for tracking the foveated inset. Our built-in logic handles positioning this node. It will copy the position and orientation of the <see cref="Godot.XROrigin3D"/> node marked as current.</para>
    /// </summary>
    public XROrigin3D GetXROrigin3D()
    {
        XROrigin3D ret = (XROrigin3D)NativeCalls.godot_icall_0_53(MethodBind0, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetXRCamera3D, 1715292258ul);

    /// <summary>
    /// <para>Returns the <see cref="Godot.XRCamera3D"/> node used for rendering the foveated inset.</para>
    /// </summary>
    public XRCamera3D GetXRCamera3D()
    {
        XRCamera3D ret = (XRCamera3D)NativeCalls.godot_icall_0_53(MethodBind1, GodotObject.GetPtr(this));
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
    public new class PropertyName : SubViewport.PropertyName
    {
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : SubViewport.MethodName
    {
        /// <summary>
        /// Cached name for the 'get_xr_origin3d' method.
        /// </summary>
        public static readonly StringName GetXROrigin3D = "get_xr_origin3d";
        /// <summary>
        /// Cached name for the 'get_xr_camera3d' method.
        /// </summary>
        public static readonly StringName GetXRCamera3D = "get_xr_camera3d";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : SubViewport.SignalName
    {
    }
}
