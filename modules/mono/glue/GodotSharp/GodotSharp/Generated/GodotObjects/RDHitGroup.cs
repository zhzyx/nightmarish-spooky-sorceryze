namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>Defines a hit group for use with <see cref="Godot.RenderingDevice.RaytracingPipelineCreate(Godot.Collections.Array{RDPipelineShader}, Godot.Collections.Array{RDPipelineShader}, Godot.Collections.Array{RDHitGroup}, uint)"/>.</para>
/// <para>A hit group combines shaders that are executed when a ray intersects geometry. It may include a closest-hit shader, any-hit shader, and intersection shader.</para>
/// <para>Hit groups are referenced by index when populating hit shader binding tables using <see cref="Godot.RenderingDevice.HitSbtRangeUpdate(Rid, long, uint, int[])"/>.</para>
/// </summary>
public partial class RDHitGroup : RefCounted
{
    /// <summary>
    /// <para>Closest-hit shader for this hit group. Executed for the closest intersection. Can be <see langword="null"/>.</para>
    /// </summary>
    public RDPipelineShader ClosestHitShader
    {
        get
        {
            return GetClosestHitShader();
        }
        set
        {
            SetClosestHitShader(value);
        }
    }

    /// <summary>
    /// <para>Any-hit shader for this hit group. Executed for each potential intersection. Can be <see langword="null"/>.</para>
    /// </summary>
    public RDPipelineShader AnyHitShader
    {
        get
        {
            return GetAnyHitShader();
        }
        set
        {
            SetAnyHitShader(value);
        }
    }

    /// <summary>
    /// <para>Intersection shader for this hit group. Required for non-triangle geometry. Must be <see langword="null"/> when using for triangle geometry.</para>
    /// </summary>
    public RDPipelineShader IntersectionShader
    {
        get
        {
            return GetIntersectionShader();
        }
        set
        {
            SetIntersectionShader(value);
        }
    }

    private static readonly System.Type CachedType = typeof(RDHitGroup);

    private static readonly StringName NativeName = "RDHitGroup";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public RDHitGroup() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal RDHitGroup(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal RDHitGroup(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetClosestHitShader, 2556777288ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetClosestHitShader(RDPipelineShader pMember)
    {
        NativeCalls.godot_icall_1_56(MethodBind0, GodotObject.GetPtr(this), GodotObject.GetPtr(pMember));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetClosestHitShader, 2937716847ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public RDPipelineShader GetClosestHitShader()
    {
        RDPipelineShader ret = (RDPipelineShader)NativeCalls.godot_icall_0_87(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetAnyHitShader, 2556777288ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetAnyHitShader(RDPipelineShader pMember)
    {
        NativeCalls.godot_icall_1_56(MethodBind2, GodotObject.GetPtr(this), GodotObject.GetPtr(pMember));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetAnyHitShader, 2937716847ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public RDPipelineShader GetAnyHitShader()
    {
        RDPipelineShader ret = (RDPipelineShader)NativeCalls.godot_icall_0_87(MethodBind3, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetIntersectionShader, 2556777288ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetIntersectionShader(RDPipelineShader pMember)
    {
        NativeCalls.godot_icall_1_56(MethodBind4, GodotObject.GetPtr(this), GodotObject.GetPtr(pMember));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetIntersectionShader, 2937716847ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public RDPipelineShader GetIntersectionShader()
    {
        RDPipelineShader ret = (RDPipelineShader)NativeCalls.godot_icall_0_87(MethodBind5, GodotObject.GetPtr(this));
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
        /// <summary>
        /// Cached name for the 'closest_hit_shader' property.
        /// </summary>
        public static readonly StringName ClosestHitShader = "closest_hit_shader";
        /// <summary>
        /// Cached name for the 'any_hit_shader' property.
        /// </summary>
        public static readonly StringName AnyHitShader = "any_hit_shader";
        /// <summary>
        /// Cached name for the 'intersection_shader' property.
        /// </summary>
        public static readonly StringName IntersectionShader = "intersection_shader";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : RefCounted.MethodName
    {
        /// <summary>
        /// Cached name for the 'set_closest_hit_shader' method.
        /// </summary>
        public static readonly StringName SetClosestHitShader = "set_closest_hit_shader";
        /// <summary>
        /// Cached name for the 'get_closest_hit_shader' method.
        /// </summary>
        public static readonly StringName GetClosestHitShader = "get_closest_hit_shader";
        /// <summary>
        /// Cached name for the 'set_any_hit_shader' method.
        /// </summary>
        public static readonly StringName SetAnyHitShader = "set_any_hit_shader";
        /// <summary>
        /// Cached name for the 'get_any_hit_shader' method.
        /// </summary>
        public static readonly StringName GetAnyHitShader = "get_any_hit_shader";
        /// <summary>
        /// Cached name for the 'set_intersection_shader' method.
        /// </summary>
        public static readonly StringName SetIntersectionShader = "set_intersection_shader";
        /// <summary>
        /// Cached name for the 'get_intersection_shader' method.
        /// </summary>
        public static readonly StringName GetIntersectionShader = "get_intersection_shader";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : RefCounted.SignalName
    {
    }
}
