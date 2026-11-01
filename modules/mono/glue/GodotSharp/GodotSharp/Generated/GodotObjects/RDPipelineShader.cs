namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>Wraps a shader resource and allows specialization constants to be applied at pipeline creation time.</para>
/// <para>Used by <see cref="Godot.RenderingDevice.RaytracingPipelineCreate(Godot.Collections.Array{RDPipelineShader}, Godot.Collections.Array{RDPipelineShader}, Godot.Collections.Array{RDHitGroup}, uint)"/> for ray generation, miss, and hit shaders. The pipeline selects the required shader stage automatically.</para>
/// </summary>
public partial class RDPipelineShader : RefCounted
{
    /// <summary>
    /// <para>Shader resource. The required stage is selected by the pipeline.</para>
    /// </summary>
    public Rid Shader
    {
        get
        {
            return GetShader();
        }
        set
        {
            SetShader(value);
        }
    }

    /// <summary>
    /// <para>Specialization constants applied to the selected shader stage at pipeline creation time.</para>
    /// </summary>
    public Godot.Collections.Array<RDPipelineSpecializationConstant> SpecializationConstants
    {
        get
        {
            return GetSpecializationConstants();
        }
        set
        {
            SetSpecializationConstants(value);
        }
    }

    private static readonly System.Type CachedType = typeof(RDPipelineShader);

    private static readonly StringName NativeName = "RDPipelineShader";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public RDPipelineShader() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal RDPipelineShader(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal RDPipelineShader(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetShader, 2722037293ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetShader(Rid pMember)
    {
        NativeCalls.godot_icall_1_63(MethodBind0, GodotObject.GetPtr(this), pMember);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetShader, 2944877500ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Rid GetShader()
    {
        Rid ret = NativeCalls.godot_icall_0_267(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetSpecializationConstants, 381264803ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetSpecializationConstants(Godot.Collections.Array<RDPipelineSpecializationConstant> specializationConstants)
    {
        NativeCalls.godot_icall_1_163(MethodBind2, GodotObject.GetPtr(this), (godot_array)(specializationConstants ?? new()).NativeValue);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetSpecializationConstants, 3995934104ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Godot.Collections.Array<RDPipelineSpecializationConstant> GetSpecializationConstants()
    {
        Godot.Collections.Array<RDPipelineSpecializationConstant> ret = new Godot.Collections.Array<RDPipelineSpecializationConstant>(NativeCalls.godot_icall_0_146(MethodBind3, GodotObject.GetPtr(this)));
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
        /// Cached name for the 'shader' property.
        /// </summary>
        public static readonly StringName Shader = "shader";
        /// <summary>
        /// Cached name for the 'specialization_constants' property.
        /// </summary>
        public static readonly StringName SpecializationConstants = "specialization_constants";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : RefCounted.MethodName
    {
        /// <summary>
        /// Cached name for the 'set_shader' method.
        /// </summary>
        public static readonly StringName SetShader = "set_shader";
        /// <summary>
        /// Cached name for the 'get_shader' method.
        /// </summary>
        public static readonly StringName GetShader = "get_shader";
        /// <summary>
        /// Cached name for the 'set_specialization_constants' method.
        /// </summary>
        public static readonly StringName SetSpecializationConstants = "set_specialization_constants";
        /// <summary>
        /// Cached name for the 'get_specialization_constants' method.
        /// </summary>
        public static readonly StringName GetSpecializationConstants = "get_specialization_constants";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : RefCounted.SignalName
    {
    }
}
