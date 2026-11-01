namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>An automatically scalable <see cref="Godot.Texture2D"/> based on an SVG image. <see cref="Godot.DpiTexture"/>s are used to automatically re-rasterize icons and other texture based UI theme elements to match viewport scale and font oversampling. See also <c>ProjectSettings.display/window/stretch/mode</c> ("canvas_items" mode) and <see cref="Godot.Viewport.OversamplingOverride"/>.</para>
/// </summary>
[GodotClassName("DPITexture")]
public partial class DpiTexture : Texture2D
{
    [EditorBrowsable(EditorBrowsableState.Never)]
#pragma warning disable CS0618 // Type or member is obsolete.
    public string _Source
    {
        get
        {
            return GetSource();
        }
        set
        {
            SetSource(value);
        }
    }
#pragma warning restore CS0618 // Type or member is obsolete.

    /// <summary>
    /// <para>If <see langword="true"/>, puts pixels of the same surrounding color in transition from transparent to opaque areas. For textures displayed with bilinear filtering, this helps to reduce the outline effect when exporting images from an image editor.</para>
    /// </summary>
    public bool FixAlphaBorder
    {
        get
        {
            return GetFixAlphaBorder();
        }
        set
        {
            SetFixAlphaBorder(value);
        }
    }

    /// <summary>
    /// <para>An alternative to fixing darkened borders with <see cref="Godot.DpiTexture.FixAlphaBorder"/> is to use premultiplied alpha. By enabling this option, the texture will be converted to this format. A premultiplied alpha texture requires specific materials to be displayed correctly:</para>
    /// <para>- In 2D, a <see cref="Godot.CanvasItemMaterial"/> will need to be created and configured to use the <see cref="Godot.CanvasItemMaterial.BlendModeEnum.PremultAlpha"/> blend mode on <see cref="Godot.CanvasItem"/>s that use this texture. In custom <c>canvas_item</c> shaders, <c>render_mode blend_premul_alpha;</c> should be used.</para>
    /// <para>- In 3D, a <see cref="Godot.BaseMaterial3D"/> will need to be created and configured to use the <see cref="Godot.BaseMaterial3D.BlendModeEnum.PremultAlpha"/> blend mode on materials that use this texture. In custom <c>spatial</c> shaders, <c>render_mode blend_premul_alpha;</c> should be used.</para>
    /// </summary>
    public bool PremultAlpha
    {
        get
        {
            return GetPremultAlpha();
        }
        set
        {
            SetPremultAlpha(value);
        }
    }

    /// <summary>
    /// <para>Texture scale. <c>1.0</c> is the original SVG size. Higher values result in a larger image.</para>
    /// </summary>
    public float BaseScale
    {
        get
        {
            return GetBaseScale();
        }
        set
        {
            SetBaseScale(value);
        }
    }

    /// <summary>
    /// <para>Overrides texture saturation.</para>
    /// </summary>
    public float Saturation
    {
        get
        {
            return GetSaturation();
        }
        set
        {
            SetSaturation(value);
        }
    }

    /// <summary>
    /// <para>If set, remaps texture colors according to <see cref="Godot.Color"/>-<see cref="Godot.Color"/> map.</para>
    /// </summary>
    public Godot.Collections.Dictionary ColorMap
    {
        get
        {
            return GetColorMap();
        }
        set
        {
            SetColorMap(value);
        }
    }

    private static readonly System.Type CachedType = typeof(DpiTexture);

    private static readonly StringName NativeName = "DPITexture";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public DpiTexture() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal DpiTexture(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal DpiTexture(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.CreateFromString, 755140520ul);

    /// <summary>
    /// <para>Creates a new <see cref="Godot.DpiTexture"/> and initializes it by allocating and setting the SVG data to <paramref name="source"/>.</para>
    /// </summary>
    public static DpiTexture CreateFromString(string source, float scale = 1.0f, float saturation = 1.0f, Godot.Collections.Dictionary colorMap = null)
    {
        DpiTexture ret = (DpiTexture)NativeCalls.godot_icall_4_398(MethodBind0, source, scale, saturation, (godot_dictionary)(colorMap ?? new()).NativeValue);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetSource, 83702148ul);

    /// <summary>
    /// <para>Sets this SVG texture's source code.</para>
    /// </summary>
    public void SetSource(string source)
    {
        NativeCalls.godot_icall_1_57(MethodBind1, GodotObject.GetPtr(this), source);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetSource, 201670096ul);

    /// <summary>
    /// <para>Returns this SVG texture's source code.</para>
    /// </summary>
    public string GetSource()
    {
        string ret = NativeCalls.godot_icall_0_58(MethodBind2, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetFixAlphaBorder, 2586408642ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetFixAlphaBorder(bool fixAlphaBorder)
    {
        NativeCalls.godot_icall_1_14(MethodBind3, GodotObject.GetPtr(this), fixAlphaBorder.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetFixAlphaBorder, 36873697ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public bool GetFixAlphaBorder()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind4, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetPremultAlpha, 2586408642ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetPremultAlpha(bool premultAlpha)
    {
        NativeCalls.godot_icall_1_14(MethodBind5, GodotObject.GetPtr(this), premultAlpha.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetPremultAlpha, 36873697ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public bool GetPremultAlpha()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind6, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetBaseScale, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetBaseScale(float baseScale)
    {
        NativeCalls.godot_icall_1_91(MethodBind7, GodotObject.GetPtr(this), baseScale);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetBaseScale, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetBaseScale()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind8, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind9 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetSaturation, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetSaturation(float saturation)
    {
        NativeCalls.godot_icall_1_91(MethodBind9, GodotObject.GetPtr(this), saturation);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind10 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetSaturation, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetSaturation()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind10, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind11 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetColorMap, 4155329257ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetColorMap(Godot.Collections.Dictionary colorMap)
    {
        NativeCalls.godot_icall_1_147(MethodBind11, GodotObject.GetPtr(this), (godot_dictionary)(colorMap ?? new()).NativeValue);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind12 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetColorMap, 3102165223ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public Godot.Collections.Dictionary GetColorMap()
    {
        Godot.Collections.Dictionary ret = NativeCalls.godot_icall_0_148(MethodBind12, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind13 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetSizeOverride, 1130785943ul);

    /// <summary>
    /// <para>Resizes the texture to the specified dimensions.</para>
    /// </summary>
    public unsafe void SetSizeOverride(Vector2I size)
    {
        NativeCalls.godot_icall_1_34(MethodBind13, GodotObject.GetPtr(this), &size);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind14 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetScaledRid, 2944877500ul);

    /// <summary>
    /// <para>Returns the <see cref="Godot.Rid"/> of the texture rasterized to match the oversampling of the currently drawn canvas item.</para>
    /// </summary>
    public Rid GetScaledRid()
    {
        Rid ret = NativeCalls.godot_icall_0_267(MethodBind14, GodotObject.GetPtr(this));
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
    public new class PropertyName : Texture2D.PropertyName
    {
        /// <summary>
        /// Cached name for the '_source' property.
        /// </summary>
        public static readonly StringName _Source = "_source";
        /// <summary>
        /// Cached name for the 'fix_alpha_border' property.
        /// </summary>
        public static readonly StringName FixAlphaBorder = "fix_alpha_border";
        /// <summary>
        /// Cached name for the 'premult_alpha' property.
        /// </summary>
        public static readonly StringName PremultAlpha = "premult_alpha";
        /// <summary>
        /// Cached name for the 'base_scale' property.
        /// </summary>
        public static readonly StringName BaseScale = "base_scale";
        /// <summary>
        /// Cached name for the 'saturation' property.
        /// </summary>
        public static readonly StringName Saturation = "saturation";
        /// <summary>
        /// Cached name for the 'color_map' property.
        /// </summary>
        public static readonly StringName ColorMap = "color_map";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : Texture2D.MethodName
    {
        /// <summary>
        /// Cached name for the 'create_from_string' method.
        /// </summary>
        public static readonly StringName CreateFromString = "create_from_string";
        /// <summary>
        /// Cached name for the 'set_source' method.
        /// </summary>
        public static readonly StringName SetSource = "set_source";
        /// <summary>
        /// Cached name for the 'get_source' method.
        /// </summary>
        public static readonly StringName GetSource = "get_source";
        /// <summary>
        /// Cached name for the 'set_fix_alpha_border' method.
        /// </summary>
        public static readonly StringName SetFixAlphaBorder = "set_fix_alpha_border";
        /// <summary>
        /// Cached name for the 'get_fix_alpha_border' method.
        /// </summary>
        public static readonly StringName GetFixAlphaBorder = "get_fix_alpha_border";
        /// <summary>
        /// Cached name for the 'set_premult_alpha' method.
        /// </summary>
        public static readonly StringName SetPremultAlpha = "set_premult_alpha";
        /// <summary>
        /// Cached name for the 'get_premult_alpha' method.
        /// </summary>
        public static readonly StringName GetPremultAlpha = "get_premult_alpha";
        /// <summary>
        /// Cached name for the 'set_base_scale' method.
        /// </summary>
        public static readonly StringName SetBaseScale = "set_base_scale";
        /// <summary>
        /// Cached name for the 'get_base_scale' method.
        /// </summary>
        public static readonly StringName GetBaseScale = "get_base_scale";
        /// <summary>
        /// Cached name for the 'set_saturation' method.
        /// </summary>
        public static readonly StringName SetSaturation = "set_saturation";
        /// <summary>
        /// Cached name for the 'get_saturation' method.
        /// </summary>
        public static readonly StringName GetSaturation = "get_saturation";
        /// <summary>
        /// Cached name for the 'set_color_map' method.
        /// </summary>
        public static readonly StringName SetColorMap = "set_color_map";
        /// <summary>
        /// Cached name for the 'get_color_map' method.
        /// </summary>
        public static readonly StringName GetColorMap = "get_color_map";
        /// <summary>
        /// Cached name for the 'set_size_override' method.
        /// </summary>
        public static readonly StringName SetSizeOverride = "set_size_override";
        /// <summary>
        /// Cached name for the 'get_scaled_rid' method.
        /// </summary>
        public static readonly StringName GetScaledRid = "get_scaled_rid";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : Texture2D.SignalName
    {
    }
}
