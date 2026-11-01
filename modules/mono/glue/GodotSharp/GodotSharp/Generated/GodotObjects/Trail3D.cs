namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>The <see cref="Godot.Trail3D"/> node draws a flat line in space, with an optional billboard mode.</para>
/// <para><b>Note:</b> This node is designed for visual effects. For solid lines, pipes, and tubes, use a <see cref="Godot.CsgPolygon3D"/> node in <see cref="Godot.CsgPolygon3D.ModeEnum.Path"/> mode.</para>
/// </summary>
public partial class Trail3D : Line3D
{
    public enum LimitModeEnum : long
    {
        /// <summary>
        /// <para>Limit the trail length in time.</para>
        /// </summary>
        Lifetime = 0,
        /// <summary>
        /// <para>Limit the trail length in size.</para>
        /// </summary>
        MaxLength = 1,
        /// <summary>
        /// <para>Represents the size of the <see cref="Godot.Trail3D.LimitModeEnum"/> enum.</para>
        /// </summary>
        Max = 2
    }

    /// <summary>
    /// <para>If <see langword="true"/>, the trail will generate new points from its head.</para>
    /// <para><b>Note:</b> Only one active trail is supported. Setting this property to <see langword="true"/> will cause the existing trail mesh to be cleared.</para>
    /// </summary>
    public bool Emitting
    {
        get
        {
            return IsEmitting();
        }
        set
        {
            SetEmitting(value);
        }
    }

    /// <summary>
    /// <para>Whether to limit the trail by lifetime or length.</para>
    /// </summary>
    public Trail3D.LimitModeEnum LimitMode
    {
        get
        {
            return GetLimitMode();
        }
        set
        {
            SetLimitMode(value);
        }
    }

    /// <summary>
    /// <para>The lifetime of the trail when <see cref="Godot.Trail3D.LimitMode"/> is <see cref="Godot.Trail3D.LimitModeEnum.Lifetime"/>.</para>
    /// </summary>
    public float Lifetime
    {
        get
        {
            return GetLifetime();
        }
        set
        {
            SetLifetime(value);
        }
    }

    /// <summary>
    /// <para>The maximum length of the trail when <see cref="Godot.Trail3D.LimitMode"/> is <see cref="Godot.Trail3D.LimitModeEnum.MaxLength"/>.</para>
    /// </summary>
    public float MaxLength
    {
        get
        {
            return GetMaxLength();
        }
        set
        {
            SetMaxLength(value);
        }
    }

    /// <summary>
    /// <para>Width of the trail.</para>
    /// </summary>
    public float Width
    {
        get
        {
            return GetWidth();
        }
        set
        {
            SetWidth(value);
        }
    }

    /// <summary>
    /// <para>Width across the length of the trail.</para>
    /// </summary>
    public Curve WidthCurve
    {
        get
        {
            return GetWidthCurve();
        }
        set
        {
            SetWidthCurve(value);
        }
    }

    /// <summary>
    /// <para>The color of the trail.</para>
    /// <para><b>Note:</b> Colors with values above <c>1.0</c> (overbright) are not supported.</para>
    /// <para><b>Note:</b> To have a visible effect on a <see cref="Godot.BaseMaterial3D"/>, <see cref="Godot.BaseMaterial3D.VertexColorUseAsAlbedo"/> <i>must</i> be <see langword="true"/>. For a <see cref="Godot.ShaderMaterial"/>, <c>ALBEDO *= COLOR.rgb;</c> must be inserted in the shader's <c>fragment()</c> function. Otherwise, <see cref="Godot.Trail3D.Color"/> will have no visible effect.</para>
    /// </summary>
    public Color Color
    {
        get
        {
            return GetColor();
        }
        set
        {
            SetColor(value);
        }
    }

    /// <summary>
    /// <para>The color gradient over the trail length.</para>
    /// <para><b>Note:</b> Colors with values above <c>1.0</c> (overbright) are not supported.</para>
    /// <para><b>Note:</b> To have a visible effect on a <see cref="Godot.BaseMaterial3D"/>, <see cref="Godot.BaseMaterial3D.VertexColorUseAsAlbedo"/> <i>must</i> be <see langword="true"/>. For a <see cref="Godot.ShaderMaterial"/>, <c>ALBEDO *= COLOR.rgb;</c> must be inserted in the shader's <c>fragment()</c> function. Otherwise, <see cref="Godot.Trail3D.Color"/> will have no visible effect.</para>
    /// </summary>
    public Gradient ColorGradient
    {
        get
        {
            return GetColorGradient();
        }
        set
        {
            SetColorGradient(value);
        }
    }

    /// <summary>
    /// <para>Alignment of the trail. Possible options are <see cref="Godot.Line3D.MeshAlignmentEnum.Local"/> for a 3D line, and <see cref="Godot.Line3D.MeshAlignmentEnum.Billboard"/> for a billboarded line.</para>
    /// </summary>
    public Line3D.MeshAlignmentEnum MeshAlignment
    {
        get
        {
            return GetMeshAlignment();
        }
        set
        {
            SetMeshAlignment(value);
        }
    }

    /// <summary>
    /// <para>The material mode for the trail.</para>
    /// </summary>
    public Line3D.MaterialModeEnum MaterialMode
    {
        get
        {
            return GetMaterialMode();
        }
        set
        {
            SetMaterialMode(value);
        }
    }

    /// <summary>
    /// <para>The material to assign to the trail mesh when <see cref="Godot.Trail3D.MaterialMode"/> is <see cref="Godot.Line3D.MaterialModeEnum.Custom"/>.</para>
    /// <para><b>Tip:</b> To preserve billboarding, use the following shader as a base:</para>
    /// <para><code>
    /// shader_type spatial;
    /// render_mode blend_mix, depth_draw_never, unshaded, skip_vertex_transform, cull_disabled;
    /// 
    /// void vertex() {
    /// 	// Billboarding code for trails
    /// 	// CUSTOM0 contains the tangent of the trail and the width.
    /// 	if (dot(CUSTOM0.xyz, CUSTOM0.xyz) &gt; 0.0) {
    /// 		vec3 p = (inverse(MODELVIEW_MATRIX) * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
    /// 		p = VERTEX - p;
    /// 		vec3 t = CUSTOM0.xyz;
    /// 		vec3 binormal = normalize(cross(p, t));
    /// 		vec3 normal = normalize(cross(t, binormal));
    /// 		vec3 tangent = normalize(cross(binormal, normal));
    /// 		VERTEX += CUSTOM0.w * binormal;
    /// 		NORMAL = normal;
    /// 		TANGENT = tangent;
    /// 		BINORMAL = binormal;
    /// 	}
    /// }
    /// 
    /// void fragment() {
    /// 	ALBEDO = COLOR.rgb;
    /// 	ALPHA = COLOR.a;
    /// }
    /// </code></para>
    /// </summary>
    public ShaderMaterial Material
    {
        get
        {
            return GetMaterial();
        }
        set
        {
            SetMaterial(value);
        }
    }

    /// <summary>
    /// <para>How to tile the UVs across the length of the trail.</para>
    /// </summary>
    public Line3D.TilingModeEnum TilingMode
    {
        get
        {
            return GetTilingMode();
        }
        set
        {
            SetTilingMode(value);
        }
    }

    /// <summary>
    /// <para>UV multiplier across the length of the trail.</para>
    /// </summary>
    public float TilingMultiplier
    {
        get
        {
            return GetTilingMultiplier();
        }
        set
        {
            SetTilingMultiplier(value);
        }
    }

    /// <summary>
    /// <para>If <see langword="true"/>, pins the UVs to their positions in space.</para>
    /// </summary>
    public bool PinUV
    {
        get
        {
            return GetPinUV();
        }
        set
        {
            SetPinUV(value);
        }
    }

    /// <summary>
    /// <para>Minimum required distance before adding a new section.</para>
    /// </summary>
    public float MinSectionLength
    {
        get
        {
            return GetMinSectionLength();
        }
        set
        {
            SetMinSectionLength(value);
        }
    }

    private static readonly System.Type CachedType = typeof(Trail3D);

    private static readonly StringName NativeName = "Trail3D";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public Trail3D() : this(false)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: false);
        }
    }

    internal Trail3D(IntPtr ptr) : this(false)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal Trail3D(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetWidth, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetWidth(float width)
    {
        NativeCalls.godot_icall_1_91(MethodBind0, GodotObject.GetPtr(this), width);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetWidth, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetWidth()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetWidthCurve, 270443179ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetWidthCurve(Curve curve)
    {
        NativeCalls.godot_icall_1_56(MethodBind2, GodotObject.GetPtr(this), GodotObject.GetPtr(curve));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetWidthCurve, 2460114913ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Curve GetWidthCurve()
    {
        Curve ret = (Curve)NativeCalls.godot_icall_0_87(MethodBind3, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetEmitting, 2586408642ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetEmitting(bool emitting)
    {
        NativeCalls.godot_icall_1_14(MethodBind4, GodotObject.GetPtr(this), emitting.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsEmitting, 36873697ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public bool IsEmitting()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind5, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetColor, 2920490490ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public unsafe void SetColor(Color color)
    {
        NativeCalls.godot_icall_1_240(MethodBind6, GodotObject.GetPtr(this), &color);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetColor, 3444240500ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Color GetColor()
    {
        Color ret = NativeCalls.godot_icall_0_241(MethodBind7, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetColorGradient, 2756054477ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetColorGradient(Gradient gradient)
    {
        NativeCalls.godot_icall_1_56(MethodBind8, GodotObject.GetPtr(this), GodotObject.GetPtr(gradient));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind9 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetColorGradient, 132272999ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Gradient GetColorGradient()
    {
        Gradient ret = (Gradient)NativeCalls.godot_icall_0_87(MethodBind9, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind10 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMaterialMode, 2165032565ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetMaterialMode(Line3D.MaterialModeEnum materialMode)
    {
        NativeCalls.godot_icall_1_38(MethodBind10, GodotObject.GetPtr(this), (int)materialMode);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind11 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMaterialMode, 3629890196ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Line3D.MaterialModeEnum GetMaterialMode()
    {
        Line3D.MaterialModeEnum ret = (Line3D.MaterialModeEnum)NativeCalls.godot_icall_0_39(MethodBind11, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind12 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMaterial, 1356176850ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetMaterial(ShaderMaterial material)
    {
        NativeCalls.godot_icall_1_56(MethodBind12, GodotObject.GetPtr(this), GodotObject.GetPtr(material));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind13 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMaterial, 953001827ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public ShaderMaterial GetMaterial()
    {
        ShaderMaterial ret = (ShaderMaterial)NativeCalls.godot_icall_0_87(MethodBind13, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind14 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMeshAlignment, 3254932473ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetMeshAlignment(Line3D.MeshAlignmentEnum alignment)
    {
        NativeCalls.godot_icall_1_38(MethodBind14, GodotObject.GetPtr(this), (int)alignment);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind15 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMeshAlignment, 603151927ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Line3D.MeshAlignmentEnum GetMeshAlignment()
    {
        Line3D.MeshAlignmentEnum ret = (Line3D.MeshAlignmentEnum)NativeCalls.godot_icall_0_39(MethodBind15, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind16 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetTilingMultiplier, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetTilingMultiplier(float tilingMultiplier)
    {
        NativeCalls.godot_icall_1_91(MethodBind16, GodotObject.GetPtr(this), tilingMultiplier);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind17 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetTilingMultiplier, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetTilingMultiplier()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind17, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind18 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetTilingMode, 3698560511ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetTilingMode(Line3D.TilingModeEnum tilingMode)
    {
        NativeCalls.godot_icall_1_38(MethodBind18, GodotObject.GetPtr(this), (int)tilingMode);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind19 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetTilingMode, 1009472955ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Line3D.TilingModeEnum GetTilingMode()
    {
        Line3D.TilingModeEnum ret = (Line3D.TilingModeEnum)NativeCalls.godot_icall_0_39(MethodBind19, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind20 = ClassDB_get_method_with_compatibility(NativeName, MethodName.Clear, 3218959716ul);

    /// <summary>
    /// <para>Clears the trail.</para>
    /// </summary>
    public void Clear()
    {
        NativeCalls.godot_icall_0_3(MethodBind20, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind21 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMinSectionLength, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetMinSectionLength(float minSectionLength)
    {
        NativeCalls.godot_icall_1_91(MethodBind21, GodotObject.GetPtr(this), minSectionLength);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind22 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMinSectionLength, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetMinSectionLength()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind22, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind23 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetLimitMode, 4181898111ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetLimitMode(Trail3D.LimitModeEnum limitMode)
    {
        NativeCalls.godot_icall_1_38(MethodBind23, GodotObject.GetPtr(this), (int)limitMode);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind24 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetLimitMode, 2679766905ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Trail3D.LimitModeEnum GetLimitMode()
    {
        Trail3D.LimitModeEnum ret = (Trail3D.LimitModeEnum)NativeCalls.godot_icall_0_39(MethodBind24, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind25 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetLifetime, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetLifetime(float lifetime)
    {
        NativeCalls.godot_icall_1_91(MethodBind25, GodotObject.GetPtr(this), lifetime);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind26 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetLifetime, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetLifetime()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind26, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind27 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMaxLength, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetMaxLength(float maxLength)
    {
        NativeCalls.godot_icall_1_91(MethodBind27, GodotObject.GetPtr(this), maxLength);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind28 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMaxLength, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetMaxLength()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind28, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind29 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetPinUV, 2586408642ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetPinUV(bool pinUV)
    {
        NativeCalls.godot_icall_1_14(MethodBind29, GodotObject.GetPtr(this), pinUV.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind30 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetPinUV, 36873697ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public bool GetPinUV()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind30, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind31 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetCurrentLength, 1740695150ul);

    /// <summary>
    /// <para>Returns the current length of the trail.</para>
    /// </summary>
    public float GetCurrentLength()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind31, GodotObject.GetPtr(this));
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
    public new class PropertyName : Line3D.PropertyName
    {
        /// <summary>
        /// Cached name for the 'emitting' property.
        /// </summary>
        public static readonly StringName Emitting = "emitting";
        /// <summary>
        /// Cached name for the 'limit_mode' property.
        /// </summary>
        public static readonly StringName LimitMode = "limit_mode";
        /// <summary>
        /// Cached name for the 'lifetime' property.
        /// </summary>
        public static readonly StringName Lifetime = "lifetime";
        /// <summary>
        /// Cached name for the 'max_length' property.
        /// </summary>
        public static readonly StringName MaxLength = "max_length";
        /// <summary>
        /// Cached name for the 'width' property.
        /// </summary>
        public static readonly StringName Width = "width";
        /// <summary>
        /// Cached name for the 'width_curve' property.
        /// </summary>
        public static readonly StringName WidthCurve = "width_curve";
        /// <summary>
        /// Cached name for the 'color' property.
        /// </summary>
        public static readonly StringName Color = "color";
        /// <summary>
        /// Cached name for the 'color_gradient' property.
        /// </summary>
        public static readonly StringName ColorGradient = "color_gradient";
        /// <summary>
        /// Cached name for the 'mesh_alignment' property.
        /// </summary>
        public static readonly StringName MeshAlignment = "mesh_alignment";
        /// <summary>
        /// Cached name for the 'material_mode' property.
        /// </summary>
        public static readonly StringName MaterialMode = "material_mode";
        /// <summary>
        /// Cached name for the 'material' property.
        /// </summary>
        public static readonly StringName Material = "material";
        /// <summary>
        /// Cached name for the 'tiling_mode' property.
        /// </summary>
        public static readonly StringName TilingMode = "tiling_mode";
        /// <summary>
        /// Cached name for the 'tiling_multiplier' property.
        /// </summary>
        public static readonly StringName TilingMultiplier = "tiling_multiplier";
        /// <summary>
        /// Cached name for the 'pin_uv' property.
        /// </summary>
        public static readonly StringName PinUV = "pin_uv";
        /// <summary>
        /// Cached name for the 'min_section_length' property.
        /// </summary>
        public static readonly StringName MinSectionLength = "min_section_length";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : Line3D.MethodName
    {
        /// <summary>
        /// Cached name for the 'set_width' method.
        /// </summary>
        public static readonly StringName SetWidth = "set_width";
        /// <summary>
        /// Cached name for the 'get_width' method.
        /// </summary>
        public static readonly StringName GetWidth = "get_width";
        /// <summary>
        /// Cached name for the 'set_width_curve' method.
        /// </summary>
        public static readonly StringName SetWidthCurve = "set_width_curve";
        /// <summary>
        /// Cached name for the 'get_width_curve' method.
        /// </summary>
        public static readonly StringName GetWidthCurve = "get_width_curve";
        /// <summary>
        /// Cached name for the 'set_emitting' method.
        /// </summary>
        public static readonly StringName SetEmitting = "set_emitting";
        /// <summary>
        /// Cached name for the 'is_emitting' method.
        /// </summary>
        public static readonly StringName IsEmitting = "is_emitting";
        /// <summary>
        /// Cached name for the 'set_color' method.
        /// </summary>
        public static readonly StringName SetColor = "set_color";
        /// <summary>
        /// Cached name for the 'get_color' method.
        /// </summary>
        public static readonly StringName GetColor = "get_color";
        /// <summary>
        /// Cached name for the 'set_color_gradient' method.
        /// </summary>
        public static readonly StringName SetColorGradient = "set_color_gradient";
        /// <summary>
        /// Cached name for the 'get_color_gradient' method.
        /// </summary>
        public static readonly StringName GetColorGradient = "get_color_gradient";
        /// <summary>
        /// Cached name for the 'set_material_mode' method.
        /// </summary>
        public static readonly StringName SetMaterialMode = "set_material_mode";
        /// <summary>
        /// Cached name for the 'get_material_mode' method.
        /// </summary>
        public static readonly StringName GetMaterialMode = "get_material_mode";
        /// <summary>
        /// Cached name for the 'set_material' method.
        /// </summary>
        public static readonly StringName SetMaterial = "set_material";
        /// <summary>
        /// Cached name for the 'get_material' method.
        /// </summary>
        public static readonly StringName GetMaterial = "get_material";
        /// <summary>
        /// Cached name for the 'set_mesh_alignment' method.
        /// </summary>
        public static readonly StringName SetMeshAlignment = "set_mesh_alignment";
        /// <summary>
        /// Cached name for the 'get_mesh_alignment' method.
        /// </summary>
        public static readonly StringName GetMeshAlignment = "get_mesh_alignment";
        /// <summary>
        /// Cached name for the 'set_tiling_multiplier' method.
        /// </summary>
        public static readonly StringName SetTilingMultiplier = "set_tiling_multiplier";
        /// <summary>
        /// Cached name for the 'get_tiling_multiplier' method.
        /// </summary>
        public static readonly StringName GetTilingMultiplier = "get_tiling_multiplier";
        /// <summary>
        /// Cached name for the 'set_tiling_mode' method.
        /// </summary>
        public static readonly StringName SetTilingMode = "set_tiling_mode";
        /// <summary>
        /// Cached name for the 'get_tiling_mode' method.
        /// </summary>
        public static readonly StringName GetTilingMode = "get_tiling_mode";
        /// <summary>
        /// Cached name for the 'clear' method.
        /// </summary>
        public static readonly StringName Clear = "clear";
        /// <summary>
        /// Cached name for the 'set_min_section_length' method.
        /// </summary>
        public static readonly StringName SetMinSectionLength = "set_min_section_length";
        /// <summary>
        /// Cached name for the 'get_min_section_length' method.
        /// </summary>
        public static readonly StringName GetMinSectionLength = "get_min_section_length";
        /// <summary>
        /// Cached name for the 'set_limit_mode' method.
        /// </summary>
        public static readonly StringName SetLimitMode = "set_limit_mode";
        /// <summary>
        /// Cached name for the 'get_limit_mode' method.
        /// </summary>
        public static readonly StringName GetLimitMode = "get_limit_mode";
        /// <summary>
        /// Cached name for the 'set_lifetime' method.
        /// </summary>
        public static readonly StringName SetLifetime = "set_lifetime";
        /// <summary>
        /// Cached name for the 'get_lifetime' method.
        /// </summary>
        public static readonly StringName GetLifetime = "get_lifetime";
        /// <summary>
        /// Cached name for the 'set_max_length' method.
        /// </summary>
        public static readonly StringName SetMaxLength = "set_max_length";
        /// <summary>
        /// Cached name for the 'get_max_length' method.
        /// </summary>
        public static readonly StringName GetMaxLength = "get_max_length";
        /// <summary>
        /// Cached name for the 'set_pin_uv' method.
        /// </summary>
        public static readonly StringName SetPinUV = "set_pin_uv";
        /// <summary>
        /// Cached name for the 'get_pin_uv' method.
        /// </summary>
        public static readonly StringName GetPinUV = "get_pin_uv";
        /// <summary>
        /// Cached name for the 'get_current_length' method.
        /// </summary>
        public static readonly StringName GetCurrentLength = "get_current_length";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : Line3D.SignalName
    {
    }
}
