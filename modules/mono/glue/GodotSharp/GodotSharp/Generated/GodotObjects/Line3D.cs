namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
public partial class Line3D : GeometryInstance3D
{
    public enum MeshAlignmentEnum : long
    {
        /// <summary>
        /// <para>Align the line normal to the local Y axis of the line node.</para>
        /// </summary>
        Local = 0,
        /// <summary>
        /// <para>Align the normal of each section of the Line3D to face the camera.</para>
        /// <para>See also <see cref="Godot.SpriteBase3D.Billboard"/> and <see cref="Godot.BaseMaterial3D.BillboardModeEnum"/></para>
        /// </summary>
        Billboard = 1,
        /// <summary>
        /// <para>Represents the size of the <see cref="Godot.Line3D.MeshAlignmentEnum"/> enum.</para>
        /// </summary>
        Max = 2
    }

    public enum TilingModeEnum : long
    {
        /// <summary>
        /// <para>Assign UVs from <c>0</c> to <c>1</c> across the length of the line.</para>
        /// </summary>
        ModeStretch = 0,
        /// <summary>
        /// <para>Assign UVs from <c>0</c> to current length, across the length of the line.</para>
        /// </summary>
        ModeTile = 1,
        /// <summary>
        /// <para>Represents the size of the <see cref="Godot.Line3D.TilingModeEnum"/> enum.</para>
        /// </summary>
        Max = 2
    }

    public enum MaterialModeEnum : long
    {
        /// <summary>
        /// <para>Assign a built-in mix material to the line.</para>
        /// </summary>
        Mix = 0,
        /// <summary>
        /// <para>Assign a built-in additive material to the line.</para>
        /// </summary>
        Add = 1,
        /// <summary>
        /// <para>Assign a custom material to the line.</para>
        /// </summary>
        Custom = 2,
        /// <summary>
        /// <para>Represents the size of the <see cref="Godot.Line3D.MaterialModeEnum"/> enum.</para>
        /// </summary>
        Max = 3
    }

    private static readonly System.Type CachedType = typeof(Line3D);

    private static readonly StringName NativeName = "Line3D";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public Line3D() : this(false)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: false);
        }
    }

    internal Line3D(IntPtr ptr) : this(false)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal Line3D(bool memoryOwn) : base(memoryOwn) { }

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
    public new class PropertyName : GeometryInstance3D.PropertyName
    {
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : GeometryInstance3D.MethodName
    {
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : GeometryInstance3D.SignalName
    {
    }
}
