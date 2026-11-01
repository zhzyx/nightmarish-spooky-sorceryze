namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>This object contains the intersection information produced by <see cref="Godot.PhysicsDirectSpaceState3D.IntersectRayInto(PhysicsRayQueryParameters3D, PhysicsIntersectRayResult3D)"/>.</para>
/// <para>After calling <see cref="Godot.PhysicsDirectSpaceState3D.IntersectRayInto(PhysicsRayQueryParameters3D, PhysicsIntersectRayResult3D)"/>, the fields of this object will be populated with the hit information if the ray intersects a shape. If no intersection occurred, the values remain unchanged from the previous state.</para>
/// <para><b>Note:</b> For optimal performance results, it is recommended to create this object in advance, store it, and reuse it for every subsequent query.</para>
/// </summary>
public partial class PhysicsIntersectRayResult3D : RefCounted
{
    /// <summary>
    /// <para>The intersection point.</para>
    /// </summary>
    public Vector3 Position
    {
        get
        {
            return GetPosition();
        }
    }

    /// <summary>
    /// <para>The object's surface normal at the intersection point, or <c>Vector3(0, 0, 0)</c> if the ray starts inside the shape and <see cref="Godot.PhysicsRayQueryParameters3D.HitFromInside"/> is <see langword="true"/>.</para>
    /// </summary>
    public Vector3 Normal
    {
        get
        {
            return GetNormal();
        }
    }

    /// <summary>
    /// <para>The intersecting object's <see cref="Godot.Rid"/>.</para>
    /// </summary>
    public Rid ColliderRid
    {
        get
        {
            return GetColliderRid();
        }
    }

    /// <summary>
    /// <para>The colliding object's ID.</para>
    /// </summary>
    public ulong ColliderId
    {
        get
        {
            return GetColliderId();
        }
    }

    /// <summary>
    /// <para>The colliding object.</para>
    /// </summary>
    public GodotObject Collider
    {
        get
        {
            return GetCollider();
        }
    }

    /// <summary>
    /// <para>The shape index of the colliding shape.</para>
    /// </summary>
    public int ColliderShape
    {
        get
        {
            return GetColliderShape();
        }
    }

    /// <summary>
    /// <para>The face index at the intersection point.</para>
    /// <para><b>Note:</b> Returns a valid number only if the intersected shape is a <see cref="Godot.ConcavePolygonShape3D"/>. Otherwise, <c>-1</c> is returned.</para>
    /// </summary>
    public int ColliderFaceIndex
    {
        get
        {
            return GetColliderFaceIndex();
        }
    }

    private static readonly System.Type CachedType = typeof(PhysicsIntersectRayResult3D);

    private static readonly StringName NativeName = "PhysicsIntersectRayResult3D";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public PhysicsIntersectRayResult3D() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal PhysicsIntersectRayResult3D(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal PhysicsIntersectRayResult3D(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetPosition, 3360562783ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Vector3 GetPosition()
    {
        Vector3 ret = NativeCalls.godot_icall_0_151(MethodBind0, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetNormal, 3360562783ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Vector3 GetNormal()
    {
        Vector3 ret = NativeCalls.godot_icall_0_151(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetColliderRid, 2944877500ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Rid GetColliderRid()
    {
        Rid ret = NativeCalls.godot_icall_0_267(MethodBind2, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetColliderId, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public ulong GetColliderId()
    {
        ulong ret = NativeCalls.godot_icall_0_162(MethodBind3, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetCollider, 1981248198ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public GodotObject GetCollider()
    {
        GodotObject ret = (GodotObject)NativeCalls.godot_icall_0_53(MethodBind4, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetColliderShape, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public int GetColliderShape()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind5, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetColliderFaceIndex, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public int GetColliderFaceIndex()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind6, GodotObject.GetPtr(this));
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
        /// Cached name for the 'position' property.
        /// </summary>
        public static readonly StringName Position = "position";
        /// <summary>
        /// Cached name for the 'normal' property.
        /// </summary>
        public static readonly StringName Normal = "normal";
        /// <summary>
        /// Cached name for the 'collider_rid' property.
        /// </summary>
        public static readonly StringName ColliderRid = "collider_rid";
        /// <summary>
        /// Cached name for the 'collider_id' property.
        /// </summary>
        public static readonly StringName ColliderId = "collider_id";
        /// <summary>
        /// Cached name for the 'collider' property.
        /// </summary>
        public static readonly StringName Collider = "collider";
        /// <summary>
        /// Cached name for the 'collider_shape' property.
        /// </summary>
        public static readonly StringName ColliderShape = "collider_shape";
        /// <summary>
        /// Cached name for the 'collider_face_index' property.
        /// </summary>
        public static readonly StringName ColliderFaceIndex = "collider_face_index";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : RefCounted.MethodName
    {
        /// <summary>
        /// Cached name for the 'get_position' method.
        /// </summary>
        public static readonly StringName GetPosition = "get_position";
        /// <summary>
        /// Cached name for the 'get_normal' method.
        /// </summary>
        public static readonly StringName GetNormal = "get_normal";
        /// <summary>
        /// Cached name for the 'get_collider_rid' method.
        /// </summary>
        public static readonly StringName GetColliderRid = "get_collider_rid";
        /// <summary>
        /// Cached name for the 'get_collider_id' method.
        /// </summary>
        public static readonly StringName GetColliderId = "get_collider_id";
        /// <summary>
        /// Cached name for the 'get_collider' method.
        /// </summary>
        public static readonly StringName GetCollider = "get_collider";
        /// <summary>
        /// Cached name for the 'get_collider_shape' method.
        /// </summary>
        public static readonly StringName GetColliderShape = "get_collider_shape";
        /// <summary>
        /// Cached name for the 'get_collider_face_index' method.
        /// </summary>
        public static readonly StringName GetColliderFaceIndex = "get_collider_face_index";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : RefCounted.SignalName
    {
    }
}
