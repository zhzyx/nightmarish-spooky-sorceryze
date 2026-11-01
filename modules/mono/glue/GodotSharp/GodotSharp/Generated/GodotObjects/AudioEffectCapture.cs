namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>Copies all audio frames, also known as "samples" or "audio samples", from the attached audio bus into its internal ring buffer. This effect does not alter the audio. Can be used for storing real-time audio data for playback, and for creating real-time audio visualizations, like an oscilloscope.</para>
/// <para>Application code should consume these audio frames from this ring buffer using <see cref="Godot.AudioEffectCapture.GetBuffer(int)"/> and process it as needed, for example to capture data from an <see cref="Godot.AudioStreamMicrophone"/>, implement application-defined effects, or to transmit audio over the network. When capturing audio data from a microphone, the format of the samples will be stereo 32-bit floating-point PCM.</para>
/// <para>Unlike <see cref="Godot.AudioEffectRecord"/>, this effect only returns the raw audio samples instead of encoding them into an <see cref="Godot.AudioStream"/>.</para>
/// </summary>
public partial class AudioEffectCapture : AudioEffect
{
    /// <summary>
    /// <para>Length of the internal ring buffer, in seconds. Higher values keep data around for longer, but require more memory. Value can range from 0.01 to 10.</para>
    /// <para><b>Note:</b> Setting the buffer length will have no effect if already initialized.</para>
    /// </summary>
    public float BufferLength
    {
        get
        {
            return GetBufferLength();
        }
        set
        {
            SetBufferLength(value);
        }
    }

    private static readonly System.Type CachedType = typeof(AudioEffectCapture);

    private static readonly StringName NativeName = "AudioEffectCapture";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public AudioEffectCapture() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal AudioEffectCapture(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal AudioEffectCapture(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.CanGetBuffer, 1116898809ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if at least <paramref name="frames"/> samples are available to read in the internal ring buffer.</para>
    /// </summary>
    public bool CanGetBuffer(int frames)
    {
        bool ret = NativeCalls.godot_icall_1_86(MethodBind0, GodotObject.GetPtr(this), frames).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetBuffer, 2649534757ul);

    /// <summary>
    /// <para>Gets the next <paramref name="frames"/> samples from the internal ring buffer.</para>
    /// <para>Returns a <see cref="Godot.Vector2"/>[] containing exactly <paramref name="frames"/> samples if available, or an empty <see cref="Godot.Vector2"/>[] if insufficient data was available.</para>
    /// <para>The samples are signed floating-point PCM between <c>-1</c> and <c>1</c>. You will have to scale them if you want to use them as 8 or 16-bit integer samples. (<c>v = 0x7fff * samples[0].x</c>)</para>
    /// </summary>
    public Vector2[] GetBuffer(int frames)
    {
        Vector2[] ret = NativeCalls.godot_icall_1_216(MethodBind1, GodotObject.GetPtr(this), frames);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.ClearBuffer, 3218959716ul);

    /// <summary>
    /// <para>Clears the internal ring buffer.</para>
    /// <para><b>Note:</b> Calling this during a capture can cause the loss of samples which causes popping in the playback.</para>
    /// </summary>
    public void ClearBuffer()
    {
        NativeCalls.godot_icall_0_3(MethodBind2, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetBufferLength, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetBufferLength(float bufferLengthSeconds)
    {
        NativeCalls.godot_icall_1_91(MethodBind3, GodotObject.GetPtr(this), bufferLengthSeconds);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetBufferLength, 191475506ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetBufferLength()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind4, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetFramesAvailable, 3905245786ul);

    /// <summary>
    /// <para>Returns the number of samples available to read using <see cref="Godot.AudioEffectCapture.GetBuffer(int)"/>.</para>
    /// </summary>
    public int GetFramesAvailable()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind5, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetDiscardedFrames, 3905245786ul);

    /// <summary>
    /// <para>Returns the number of samples discarded from the audio bus due to full buffer.</para>
    /// </summary>
    public long GetDiscardedFrames()
    {
        long ret = NativeCalls.godot_icall_0_4(MethodBind6, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetBufferLengthFrames, 3905245786ul);

    /// <summary>
    /// <para>Returns the total size of the internal ring buffer in number of samples.</para>
    /// </summary>
    public int GetBufferLengthFrames()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind7, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetPushedFrames, 3905245786ul);

    /// <summary>
    /// <para>Returns the number of samples inserted from the audio bus.</para>
    /// </summary>
    public long GetPushedFrames()
    {
        long ret = NativeCalls.godot_icall_0_4(MethodBind8, GodotObject.GetPtr(this));
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
    public new class PropertyName : AudioEffect.PropertyName
    {
        /// <summary>
        /// Cached name for the 'buffer_length' property.
        /// </summary>
        public static readonly StringName BufferLength = "buffer_length";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : AudioEffect.MethodName
    {
        /// <summary>
        /// Cached name for the 'can_get_buffer' method.
        /// </summary>
        public static readonly StringName CanGetBuffer = "can_get_buffer";
        /// <summary>
        /// Cached name for the 'get_buffer' method.
        /// </summary>
        public static readonly StringName GetBuffer = "get_buffer";
        /// <summary>
        /// Cached name for the 'clear_buffer' method.
        /// </summary>
        public static readonly StringName ClearBuffer = "clear_buffer";
        /// <summary>
        /// Cached name for the 'set_buffer_length' method.
        /// </summary>
        public static readonly StringName SetBufferLength = "set_buffer_length";
        /// <summary>
        /// Cached name for the 'get_buffer_length' method.
        /// </summary>
        public static readonly StringName GetBufferLength = "get_buffer_length";
        /// <summary>
        /// Cached name for the 'get_frames_available' method.
        /// </summary>
        public static readonly StringName GetFramesAvailable = "get_frames_available";
        /// <summary>
        /// Cached name for the 'get_discarded_frames' method.
        /// </summary>
        public static readonly StringName GetDiscardedFrames = "get_discarded_frames";
        /// <summary>
        /// Cached name for the 'get_buffer_length_frames' method.
        /// </summary>
        public static readonly StringName GetBufferLengthFrames = "get_buffer_length_frames";
        /// <summary>
        /// Cached name for the 'get_pushed_frames' method.
        /// </summary>
        public static readonly StringName GetPushedFrames = "get_pushed_frames";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : AudioEffect.SignalName
    {
    }
}
