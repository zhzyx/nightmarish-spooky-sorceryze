namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>A 2D texture that can be modified via blit calls, copying from a target texture to itself. Primarily intended to be managed in code, a user must call <see cref="Godot.DrawableTexture2D.Setup(int, int, DrawableTexture2D.DrawableFormat, Nullable{Color}, bool)"/> to initialize the state before drawing. Each <see cref="Godot.DrawableTexture2D.BlitRect(Rect2I, Texture2D, Nullable{Color}, int, Material)"/> call takes at least a rectangle, the area to draw to, and another texture, what to be drawn. The draw calls use a Texture_Blit Shader to process and calculate the result, pixel by pixel. Users can supply their own ShaderMaterial with custom Texture_Blit shaders for more complex behaviors.</para>
/// </summary>
public partial class DrawableTexture2D : Texture2D
{
    public enum DrawableFormat : long
    {
        /// <summary>
        /// <para>OpenGL texture format RGBA with four components, each with a bitdepth of 8.</para>
        /// </summary>
        Rgba8 = 0,
        /// <summary>
        /// <para>OpenGL texture format RGBA with four components, each with a bitdepth of 8.</para>
        /// <para>When drawn to, a linear to sRGB color encoding conversion is performed.</para>
        /// </summary>
        Rgba8Srgb = 1,
        /// <summary>
        /// <para>OpenGL texture format GL_RGBA16F where there are four components, each a 16-bit "half-precision" floating-point value.</para>
        /// </summary>
        Rgbah = 2,
        /// <summary>
        /// <para>OpenGL texture format GL_RGBA32F where there are four components, each a 32-bit floating-point value.</para>
        /// </summary>
        Rgbaf = 3
    }

    private static readonly System.Type CachedType = typeof(DrawableTexture2D);

    private static readonly StringName NativeName = "DrawableTexture2D";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public DrawableTexture2D() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal DrawableTexture2D(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal DrawableTexture2D(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetFormat, 2875673594ul);

    /// <summary>
    /// <para>Sets the format of this DrawableTexture.</para>
    /// </summary>
    public void SetFormat(DrawableTexture2D.DrawableFormat format)
    {
        NativeCalls.godot_icall_1_38(MethodBind0, GodotObject.GetPtr(this), (int)format);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetUseMipmaps, 2586408642ul);

    /// <summary>
    /// <para>Sets if mipmaps should be used on this DrawableTexture.</para>
    /// </summary>
    public void SetUseMipmaps(bool mipmaps)
    {
        NativeCalls.godot_icall_1_14(MethodBind1, GodotObject.GetPtr(this), mipmaps.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetUseMipmaps, 36873697ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if mipmaps are set to be used on this DrawableTexture.</para>
    /// </summary>
    public bool GetUseMipmaps()
    {
        bool ret = NativeCalls.godot_icall_0_15(MethodBind2, GodotObject.GetPtr(this)).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.Setup, 674365339ul);

    /// <summary>
    /// <para>Initializes the DrawableTexture to a White texture of the given <paramref name="width"/>, <paramref name="height"/>, and <paramref name="format"/>.</para>
    /// </summary>
    /// <param name="color">If the parameter is null, then the default value is <c>new Color(1.0f, 1.0f, 1.0f, 1.0f)</c>.</param>
    public unsafe void Setup(int width, int height, DrawableTexture2D.DrawableFormat format, Nullable<Color> color = null, bool useMipmaps = false)
    {
        Color colorOrDefVal = color.HasValue ? color.Value : new Color(1.0f, 1.0f, 1.0f, 1.0f);
        NativeCalls.godot_icall_5_465(MethodBind3, GodotObject.GetPtr(this), width, height, (int)format, &colorOrDefVal, useMipmaps.ToGodotBool());
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.BlitRect, 319217173ul);

    /// <summary>
    /// <para>Draws to given <paramref name="rect"/> on this texture by copying from the given <paramref name="source"/>. A <paramref name="modulate"/> color can be passed in for the shader to use, but defaults to White. The <paramref name="mipmap"/> value can specify a draw to a lower mipmap level. The <paramref name="material"/> parameter can take a ShaderMaterial with a TextureBlit Shader for custom drawing behavior.</para>
    /// </summary>
    /// <param name="modulate">If the parameter is null, then the default value is <c>new Color(1.0f, 1.0f, 1.0f, 1.0f)</c>.</param>
    public unsafe void BlitRect(Rect2I rect, Texture2D source, Nullable<Color> modulate = null, int mipmap = 0, Material material = null)
    {
        Color modulateOrDefVal = modulate.HasValue ? modulate.Value : new Color(1.0f, 1.0f, 1.0f, 1.0f);
        NativeCalls.godot_icall_5_466(MethodBind4, GodotObject.GetPtr(this), &rect, GodotObject.GetPtr(source), &modulateOrDefVal, mipmap, GodotObject.GetPtr(material));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.BlitRectMulti, 3074783066ul);

    /// <summary>
    /// <para>Draws to the given <paramref name="rect"/> on this texture, as well as on up to 3 DrawableTexture <paramref name="extraTargets"/>. All <paramref name="extraTargets"/> must be the same size and DrawableFormat as the original target, otherwise the Shader may fail. Expects up to 4 Texture <paramref name="sources"/>, but will replace missing <paramref name="sources"/> with default Black Textures.</para>
    /// </summary>
    /// <param name="modulate">If the parameter is null, then the default value is <c>new Color(1.0f, 1.0f, 1.0f, 1.0f)</c>.</param>
    public unsafe void BlitRectMulti(Rect2I rect, Godot.Collections.Array<Texture2D> sources, Godot.Collections.Array<DrawableTexture2D> extraTargets, Nullable<Color> modulate = null, int mipmap = 0, Material material = null)
    {
        Color modulateOrDefVal = modulate.HasValue ? modulate.Value : new Color(1.0f, 1.0f, 1.0f, 1.0f);
        NativeCalls.godot_icall_6_467(MethodBind5, GodotObject.GetPtr(this), &rect, (godot_array)(sources ?? new()).NativeValue, (godot_array)(extraTargets ?? new()).NativeValue, &modulateOrDefVal, mipmap, GodotObject.GetPtr(material));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GenerateMipmaps, 3218959716ul);

    /// <summary>
    /// <para>Re-calculates the mipmaps for this texture on demand.</para>
    /// </summary>
    public void GenerateMipmaps()
    {
        NativeCalls.godot_icall_0_3(MethodBind6, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
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
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : Texture2D.MethodName
    {
        /// <summary>
        /// Cached name for the 'set_format' method.
        /// </summary>
        public static readonly StringName SetFormat = "set_format";
        /// <summary>
        /// Cached name for the 'set_use_mipmaps' method.
        /// </summary>
        public static readonly StringName SetUseMipmaps = "set_use_mipmaps";
        /// <summary>
        /// Cached name for the 'get_use_mipmaps' method.
        /// </summary>
        public static readonly StringName GetUseMipmaps = "get_use_mipmaps";
        /// <summary>
        /// Cached name for the 'setup' method.
        /// </summary>
        public static readonly StringName Setup = "setup";
        /// <summary>
        /// Cached name for the 'blit_rect' method.
        /// </summary>
        public static readonly StringName BlitRect = "blit_rect";
        /// <summary>
        /// Cached name for the 'blit_rect_multi' method.
        /// </summary>
        public static readonly StringName BlitRectMulti = "blit_rect_multi";
        /// <summary>
        /// Cached name for the 'generate_mipmaps' method.
        /// </summary>
        public static readonly StringName GenerateMipmaps = "generate_mipmaps";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : Texture2D.SignalName
    {
    }
}
