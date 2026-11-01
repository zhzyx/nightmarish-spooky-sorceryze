namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>An area light is a type of <see cref="Godot.Light3D"/> node that emits light over a two-dimensional area, in the shape of a rectangle. The light is attenuated throughout the distance. This attenuation can be configured by changing the energy, <see cref="Godot.AreaLight3D.AreaAttenuation"/>, and <see cref="Godot.AreaLight3D.AreaRange"/>.</para>
/// <para>Light is emitted in the -Z direction of the node's global basis. For an unrotated light, this means that the light is emitted forwards, illuminating the front side of a 3D model (see <c>Vector3.FORWARD</c> and <c>Vector3.MODEL_FRONT</c>).</para>
/// <para>Area lights can cast soft shadows using PCSS, which you can control by tweaking the size parameter. The shadow map is drawn from the center of the light.</para>
/// <para><b>Note:</b> Area lights have limited support in the Mobile and Compatibility renderers. In the Mobile renderer, the size of the penumbra doesn't vary as it should with PCSS. In Compatibility, area lights cannot cast shadows.</para>
/// <para><b>Warning:</b> Shadows cast by an area light may look incorrect if the object casting shadows doesn't have enough subdivisions and it's very close to the area light. This is the same limitation as the Dual Paraboloid shadow mode on an <see cref="Godot.OmniLight3D"/>.</para>
/// <para><b>Performance:</b> Area lights are more demanding on the GPU compared to omni and spot lights. In Forward+, there is an additional GPU cost on <i>all</i> rendered objects as soon as one area light is present in the view frustum (due to the nature of clustered lighting). Consider using them only for cinematics or when targeting high-end devices.</para>
/// </summary>
public partial class AreaLight3D : Light3D
{
    /// <summary>
    /// <para>The range of the area in meters. This determines the maximum distance from any point on the area at which the area can still emit light.</para>
    /// </summary>
    public float AreaRange
    {
        get
        {
            return GetParam((Light3D.Param)(4));
        }
        set
        {
            SetParam((Light3D.Param)(4), value);
        }
    }

    /// <summary>
    /// <para>Controls the distance attenuation function for this area light.</para>
    /// <para>A value of <c>0.0</c> will maintain a constant brightness through most of the range, but will smoothly attenuate the light at the edge of the range. Use a value of <c>2.0</c> for physically accurate lights as it results in the proper inverse square attenuation.</para>
    /// <para><b>Note:</b> Setting attenuation to <c>2.0</c> or higher may result in distant objects receiving minimal light, even when within range. For example, with a range of <c>4096</c>, an object at <c>100</c> units is attenuated by a factor of <c>0.0001</c>. With a default brightness of <c>1</c>, the light would not be visible at that distance.</para>
    /// <para><b>Note:</b> Using negative values or values higher than <c>10.0</c> may lead to unexpected results.</para>
    /// </summary>
    public float AreaAttenuation
    {
        get
        {
            return GetParam((Light3D.Param)(6));
        }
        set
        {
            SetParam((Light3D.Param)(6), value);
        }
    }

    /// <summary>
    /// <para>Defines whether the energy is normalized (divided) by the surface area of the light. If set to <see langword="true"/>, changing the size does not affect the total energy output, and does not dramatically alter the brightness of the scene.</para>
    /// </summary>
    public bool AreaNormalizeEnergy
    {
        get
        {
            return IsAreaNormalizingEnergy();
        }
        set
        {
            SetAreaNormalizeEnergy(value);
        }
    }

    /// <summary>
    /// <para>The extents (width and height) of the area in meters.</para>
    /// </summary>
    public Vector2 AreaSize
    {
        get
        {
            return GetAreaSize();
        }
        set
        {
            SetAreaSize(value);
        }
    }

    /// <summary>
    /// <para>An optional texture to use as a light source. Changing the texture at runtime might impact performance, as it needs to be drawn to the area light atlas with filtered mipmaps.</para>
    /// <para>If no texture is assigned, the area light emits uniform light across its surface.</para>
    /// <para><b>Note:</b> Area light textures are only supported in the Forward+ and Mobile rendering methods, not Compatibility. To reduce the performance impact of switching textures at runtime, make sure each dimension of an area texture is either a multiple of 128 pixels, or a power of two. This removes the need for a scaling pass, which slows down texture changes. The textures don't necessarily have to be square to be optimal. Examples of optimal texture sizes include 32×64, 128×128, and 256×384.</para>
    /// </summary>
    public Texture2D AreaTexture
    {
        get
        {
            return GetAreaTexture();
        }
        set
        {
            SetAreaTexture(value);
        }
    }

    private static readonly System.Type CachedType = typeof(AreaLight3D);

    private static readonly StringName NativeName = "AreaLight3D";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public AreaLight3D() : this(false)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: false);
        }
    }

    internal AreaLight3D(IntPtr ptr) : this(false)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal AreaLight3D(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetAreaTexture, 4051416890ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetAreaTexture(Texture2D texture)
    {
        NativeCalls.godot_icall_1_56(MethodBind0, GodotObject.GetPtr(this), GodotObject.GetPtr(texture));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetAreaTexture, 3635182373ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Texture2D GetAreaTexture()
    {
        Texture2D ret = (Texture2D)NativeCalls.godot_icall_0_87(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetAreaSize, 743155724ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public unsafe void SetAreaSize(Vector2 areaSize)
    {
        NativeCalls.godot_icall_1_36(MethodBind2, GodotObject.GetPtr(this), &areaSize);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetAreaSize, 3341600327ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Vector2 GetAreaSize()
    {
        Vector2 ret = NativeCalls.godot_icall_0_37(MethodBind3, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetAreaNormalizeEnergy, 2586408642ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetAreaNormalizeEnergy(bool enable)
    {
        NativeCalls.godot_icall_1_14(MethodBind4, GodotObject.GetPtr(this), enable.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsAreaNormalizingEnergy, 36873697ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public bool IsAreaNormalizingEnergy()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind5, GodotObject.GetPtr(this)).ToBool();
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
    public new class PropertyName : Light3D.PropertyName
    {
        /// <summary>
        /// Cached name for the 'area_range' property.
        /// </summary>
        public static readonly StringName AreaRange = "area_range";
        /// <summary>
        /// Cached name for the 'area_attenuation' property.
        /// </summary>
        public static readonly StringName AreaAttenuation = "area_attenuation";
        /// <summary>
        /// Cached name for the 'area_normalize_energy' property.
        /// </summary>
        public static readonly StringName AreaNormalizeEnergy = "area_normalize_energy";
        /// <summary>
        /// Cached name for the 'area_size' property.
        /// </summary>
        public static readonly StringName AreaSize = "area_size";
        /// <summary>
        /// Cached name for the 'area_texture' property.
        /// </summary>
        public static readonly StringName AreaTexture = "area_texture";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : Light3D.MethodName
    {
        /// <summary>
        /// Cached name for the 'set_area_texture' method.
        /// </summary>
        public static readonly StringName SetAreaTexture = "set_area_texture";
        /// <summary>
        /// Cached name for the 'get_area_texture' method.
        /// </summary>
        public static readonly StringName GetAreaTexture = "get_area_texture";
        /// <summary>
        /// Cached name for the 'set_area_size' method.
        /// </summary>
        public static readonly StringName SetAreaSize = "set_area_size";
        /// <summary>
        /// Cached name for the 'get_area_size' method.
        /// </summary>
        public static readonly StringName GetAreaSize = "get_area_size";
        /// <summary>
        /// Cached name for the 'set_area_normalize_energy' method.
        /// </summary>
        public static readonly StringName SetAreaNormalizeEnergy = "set_area_normalize_energy";
        /// <summary>
        /// Cached name for the 'is_area_normalizing_energy' method.
        /// </summary>
        public static readonly StringName IsAreaNormalizingEnergy = "is_area_normalizing_energy";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : Light3D.SignalName
    {
    }
}
