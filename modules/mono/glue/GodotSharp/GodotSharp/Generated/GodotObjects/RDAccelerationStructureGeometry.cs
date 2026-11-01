namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para><see cref="Godot.RDAccelerationStructureGeometry"/> describes a set of triangles used as raytracing geometry in the <see cref="Godot.RenderingDevice.BlasCreate(Godot.Collections.Array{RDAccelerationStructureGeometry}, RenderingDevice.AccelerationStructureFlagBits)"/> method.</para>
/// <para>The geometry is always in triangle list form, either indexed or non-indexed. Triangle strips are not supported.</para>
/// </summary>
public partial class RDAccelerationStructureGeometry : RefCounted
{
    /// <summary>
    /// <para>Flags for the geometry.</para>
    /// </summary>
    public RenderingDevice.AccelerationStructureGeometryFlagBits Flags
    {
        get
        {
            return GetFlags();
        }
        set
        {
            SetFlags(value);
        }
    }

    /// <summary>
    /// <para>Buffer containing vertices.</para>
    /// </summary>
    public Rid VertexBuffer
    {
        get
        {
            return GetVertexBuffer();
        }
        set
        {
            SetVertexBuffer(value);
        }
    }

    /// <summary>
    /// <para>Byte offset of the first vertex in <see cref="Godot.RDAccelerationStructureGeometry.VertexBuffer"/>.</para>
    /// </summary>
    public uint VertexOffset
    {
        get
        {
            return GetVertexOffset();
        }
        set
        {
            SetVertexOffset(value);
        }
    }

    /// <summary>
    /// <para>Number of bytes between each vertex in <see cref="Godot.RDAccelerationStructureGeometry.VertexBuffer"/>.</para>
    /// </summary>
    public uint VertexStride
    {
        get
        {
            return GetVertexStride();
        }
        set
        {
            SetVertexStride(value);
        }
    }

    /// <summary>
    /// <para>Number of vertices used by this geometry in <see cref="Godot.RDAccelerationStructureGeometry.VertexBuffer"/>.</para>
    /// </summary>
    public uint VertexCount
    {
        get
        {
            return GetVertexCount();
        }
        set
        {
            SetVertexCount(value);
        }
    }

    /// <summary>
    /// <para>Format of the vertices in <see cref="Godot.RDAccelerationStructureGeometry.VertexBuffer"/>.</para>
    /// </summary>
    public RenderingDevice.DataFormat VertexFormat
    {
        get
        {
            return GetVertexFormat();
        }
        set
        {
            SetVertexFormat(value);
        }
    }

    /// <summary>
    /// <para>Buffer containing vertex indices. If <see langword="null"/>, triangles are non-indexed.</para>
    /// </summary>
    public Rid IndexBuffer
    {
        get
        {
            return GetIndexBuffer();
        }
        set
        {
            SetIndexBuffer(value);
        }
    }

    /// <summary>
    /// <para>Byte offset of the first index in <see cref="Godot.RDAccelerationStructureGeometry.IndexBuffer"/>.</para>
    /// </summary>
    public uint IndexOffset
    {
        get
        {
            return GetIndexOffset();
        }
        set
        {
            SetIndexOffset(value);
        }
    }

    /// <summary>
    /// <para>Number of indices used by this geometry in <see cref="Godot.RDAccelerationStructureGeometry.IndexBuffer"/>.</para>
    /// </summary>
    public uint IndexCount
    {
        get
        {
            return GetIndexCount();
        }
        set
        {
            SetIndexCount(value);
        }
    }

    private static readonly System.Type CachedType = typeof(RDAccelerationStructureGeometry);

    private static readonly StringName NativeName = "RDAccelerationStructureGeometry";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public RDAccelerationStructureGeometry() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal RDAccelerationStructureGeometry(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal RDAccelerationStructureGeometry(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetFlags, 1046628555ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetFlags(RenderingDevice.AccelerationStructureGeometryFlagBits pMember)
    {
        NativeCalls.godot_icall_1_38(MethodBind0, GodotObject.GetPtr(this), (int)pMember);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetFlags, 1694887119ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public RenderingDevice.AccelerationStructureGeometryFlagBits GetFlags()
    {
        RenderingDevice.AccelerationStructureGeometryFlagBits ret = (RenderingDevice.AccelerationStructureGeometryFlagBits)NativeCalls.godot_icall_0_39(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetVertexBuffer, 2722037293ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetVertexBuffer(Rid pMember)
    {
        NativeCalls.godot_icall_1_63(MethodBind2, GodotObject.GetPtr(this), pMember);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetVertexBuffer, 2944877500ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Rid GetVertexBuffer()
    {
        Rid ret = NativeCalls.godot_icall_0_267(MethodBind3, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetVertexOffset, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetVertexOffset(uint pMember)
    {
        NativeCalls.godot_icall_1_234(MethodBind4, GodotObject.GetPtr(this), pMember);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetVertexOffset, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public uint GetVertexOffset()
    {
        uint ret = NativeCalls.godot_icall_0_235(MethodBind5, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetVertexStride, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetVertexStride(uint pMember)
    {
        NativeCalls.godot_icall_1_234(MethodBind6, GodotObject.GetPtr(this), pMember);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetVertexStride, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public uint GetVertexStride()
    {
        uint ret = NativeCalls.godot_icall_0_235(MethodBind7, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetVertexCount, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetVertexCount(uint pMember)
    {
        NativeCalls.godot_icall_1_234(MethodBind8, GodotObject.GetPtr(this), pMember);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind9 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetVertexCount, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public uint GetVertexCount()
    {
        uint ret = NativeCalls.godot_icall_0_235(MethodBind9, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind10 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetVertexFormat, 565531219ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetVertexFormat(RenderingDevice.DataFormat pMember)
    {
        NativeCalls.godot_icall_1_38(MethodBind10, GodotObject.GetPtr(this), (int)pMember);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind11 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetVertexFormat, 2235804183ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public RenderingDevice.DataFormat GetVertexFormat()
    {
        RenderingDevice.DataFormat ret = (RenderingDevice.DataFormat)NativeCalls.godot_icall_0_39(MethodBind11, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind12 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetIndexBuffer, 2722037293ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetIndexBuffer(Rid pMember)
    {
        NativeCalls.godot_icall_1_63(MethodBind12, GodotObject.GetPtr(this), pMember);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind13 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetIndexBuffer, 2944877500ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Rid GetIndexBuffer()
    {
        Rid ret = NativeCalls.godot_icall_0_267(MethodBind13, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind14 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetIndexOffset, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetIndexOffset(uint pMember)
    {
        NativeCalls.godot_icall_1_234(MethodBind14, GodotObject.GetPtr(this), pMember);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind15 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetIndexOffset, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public uint GetIndexOffset()
    {
        uint ret = NativeCalls.godot_icall_0_235(MethodBind15, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind16 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetIndexCount, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetIndexCount(uint pMember)
    {
        NativeCalls.godot_icall_1_234(MethodBind16, GodotObject.GetPtr(this), pMember);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind17 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetIndexCount, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public uint GetIndexCount()
    {
        uint ret = NativeCalls.godot_icall_0_235(MethodBind17, GodotObject.GetPtr(this));
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
        /// Cached name for the 'flags' property.
        /// </summary>
        public static readonly StringName Flags = "flags";
        /// <summary>
        /// Cached name for the 'vertex_buffer' property.
        /// </summary>
        public static readonly StringName VertexBuffer = "vertex_buffer";
        /// <summary>
        /// Cached name for the 'vertex_offset' property.
        /// </summary>
        public static readonly StringName VertexOffset = "vertex_offset";
        /// <summary>
        /// Cached name for the 'vertex_stride' property.
        /// </summary>
        public static readonly StringName VertexStride = "vertex_stride";
        /// <summary>
        /// Cached name for the 'vertex_count' property.
        /// </summary>
        public static readonly StringName VertexCount = "vertex_count";
        /// <summary>
        /// Cached name for the 'vertex_format' property.
        /// </summary>
        public static readonly StringName VertexFormat = "vertex_format";
        /// <summary>
        /// Cached name for the 'index_buffer' property.
        /// </summary>
        public static readonly StringName IndexBuffer = "index_buffer";
        /// <summary>
        /// Cached name for the 'index_offset' property.
        /// </summary>
        public static readonly StringName IndexOffset = "index_offset";
        /// <summary>
        /// Cached name for the 'index_count' property.
        /// </summary>
        public static readonly StringName IndexCount = "index_count";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : RefCounted.MethodName
    {
        /// <summary>
        /// Cached name for the 'set_flags' method.
        /// </summary>
        public static readonly StringName SetFlags = "set_flags";
        /// <summary>
        /// Cached name for the 'get_flags' method.
        /// </summary>
        public static readonly StringName GetFlags = "get_flags";
        /// <summary>
        /// Cached name for the 'set_vertex_buffer' method.
        /// </summary>
        public static readonly StringName SetVertexBuffer = "set_vertex_buffer";
        /// <summary>
        /// Cached name for the 'get_vertex_buffer' method.
        /// </summary>
        public static readonly StringName GetVertexBuffer = "get_vertex_buffer";
        /// <summary>
        /// Cached name for the 'set_vertex_offset' method.
        /// </summary>
        public static readonly StringName SetVertexOffset = "set_vertex_offset";
        /// <summary>
        /// Cached name for the 'get_vertex_offset' method.
        /// </summary>
        public static readonly StringName GetVertexOffset = "get_vertex_offset";
        /// <summary>
        /// Cached name for the 'set_vertex_stride' method.
        /// </summary>
        public static readonly StringName SetVertexStride = "set_vertex_stride";
        /// <summary>
        /// Cached name for the 'get_vertex_stride' method.
        /// </summary>
        public static readonly StringName GetVertexStride = "get_vertex_stride";
        /// <summary>
        /// Cached name for the 'set_vertex_count' method.
        /// </summary>
        public static readonly StringName SetVertexCount = "set_vertex_count";
        /// <summary>
        /// Cached name for the 'get_vertex_count' method.
        /// </summary>
        public static readonly StringName GetVertexCount = "get_vertex_count";
        /// <summary>
        /// Cached name for the 'set_vertex_format' method.
        /// </summary>
        public static readonly StringName SetVertexFormat = "set_vertex_format";
        /// <summary>
        /// Cached name for the 'get_vertex_format' method.
        /// </summary>
        public static readonly StringName GetVertexFormat = "get_vertex_format";
        /// <summary>
        /// Cached name for the 'set_index_buffer' method.
        /// </summary>
        public static readonly StringName SetIndexBuffer = "set_index_buffer";
        /// <summary>
        /// Cached name for the 'get_index_buffer' method.
        /// </summary>
        public static readonly StringName GetIndexBuffer = "get_index_buffer";
        /// <summary>
        /// Cached name for the 'set_index_offset' method.
        /// </summary>
        public static readonly StringName SetIndexOffset = "set_index_offset";
        /// <summary>
        /// Cached name for the 'get_index_offset' method.
        /// </summary>
        public static readonly StringName GetIndexOffset = "get_index_offset";
        /// <summary>
        /// Cached name for the 'set_index_count' method.
        /// </summary>
        public static readonly StringName SetIndexCount = "set_index_count";
        /// <summary>
        /// Cached name for the 'get_index_count' method.
        /// </summary>
        public static readonly StringName GetIndexCount = "get_index_count";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : RefCounted.SignalName
    {
    }
}
