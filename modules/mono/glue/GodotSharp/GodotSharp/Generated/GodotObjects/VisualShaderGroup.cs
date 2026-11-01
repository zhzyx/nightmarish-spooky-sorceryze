namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>A <see cref="Godot.VisualShaderGroup"/> encapsulates a graph of <see cref="Godot.VisualShaderNode"/>s into a reusable component. It defines its own input and output ports, which become the interface when the group is used as a <see cref="Godot.VisualShaderNodeGroup"/> node inside a <see cref="Godot.VisualShader"/> or another <see cref="Godot.VisualShaderGroup"/>.</para>
/// <para>Since an actual shader function is created for each <see cref="Godot.VisualShaderGroup"/>, you can only use global built-in variables. Parameter and Varying related nodes are not allowed.</para>
/// <para>If the group contains nodes that are incompatible with the shader context it is used in (e.g. particle nodes in a spatial shader), the group's outputs will silently fall back to default values.</para>
/// </summary>
public partial class VisualShaderGroup : Resource
{
    /// <summary>
    /// <para>The display name of this group. This name is shown as the caption of the <see cref="Godot.VisualShaderNodeGroup"/> node in the editor.</para>
    /// </summary>
    public string GroupName
    {
        get
        {
            return GetGroupName();
        }
        set
        {
            SetGroupName(value);
        }
    }

    /// <summary>
    /// <para>The number of input ports defined for this group. Shrinking the array removes the trailing ports along with any connections made to them.</para>
    /// </summary>
    public int InputPortCount
    {
        get
        {
            return GetInputPortCount();
        }
        set
        {
            SetInputPortCount(value);
        }
    }

    /// <summary>
    /// <para>The number of output ports defined for this group. Shrinking the array removes the trailing ports along with any connections made to them.</para>
    /// </summary>
    public int OutputPortCount
    {
        get
        {
            return GetOutputPortCount();
        }
        set
        {
            SetOutputPortCount(value);
        }
    }

    private static readonly System.Type CachedType = typeof(VisualShaderGroup);

    private static readonly StringName NativeName = "VisualShaderGroup";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public VisualShaderGroup() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal VisualShaderGroup(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal VisualShaderGroup(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetGroupName, 83702148ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetGroupName(string name)
    {
        NativeCalls.godot_icall_1_57(MethodBind0, GodotObject.GetPtr(this), name);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetGroupName, 201670096ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public string GetGroupName()
    {
        string ret = NativeCalls.godot_icall_0_58(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.InsertInputPort, 3880595796ul);

    /// <summary>
    /// <para>Inserts an input port at the given <paramref name="id"/> with the specified <paramref name="type"/> and <paramref name="name"/>.</para>
    /// <para>Returns the validated port name, which may differ from <paramref name="name"/> if a port with the same name already exists. Port names must be unique across both input and output ports.</para>
    /// </summary>
    public string InsertInputPort(int id, VisualShaderNode.PortType type, string name)
    {
        string ret = NativeCalls.godot_icall_3_1557(MethodBind2, GodotObject.GetPtr(this), id, (int)type, name);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.RemoveInputPort, 1286410249ul);

    /// <summary>
    /// <para>Removes the input port at the given <paramref name="id"/>.</para>
    /// </summary>
    public void RemoveInputPort(int id)
    {
        NativeCalls.godot_icall_1_38(MethodBind3, GodotObject.GetPtr(this), id);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.MoveInputPort, 3937882851ul);

    /// <summary>
    /// <para>Moves the input port at index <paramref name="from"/> to index <paramref name="to"/>. Connections from input nodes inside the group will be updated accordingly.</para>
    /// </summary>
    public void MoveInputPort(int from, int to)
    {
        NativeCalls.godot_icall_2_84(MethodBind4, GodotObject.GetPtr(this), from, to);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetInputPortName, 501894301ul);

    /// <summary>
    /// <para>Sets the name of the input port at the given <paramref name="id"/>.</para>
    /// </summary>
    public void SetInputPortName(int id, string name)
    {
        NativeCalls.godot_icall_2_206(MethodBind5, GodotObject.GetPtr(this), id, name);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetInputPortType, 1959648900ul);

    /// <summary>
    /// <para>Sets the type of the input port at the given <paramref name="id"/>.</para>
    /// </summary>
    public void SetInputPortType(int id, VisualShaderNode.PortType type)
    {
        NativeCalls.godot_icall_2_84(MethodBind6, GodotObject.GetPtr(this), id, (int)type);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetInputPortCount, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetInputPortCount(int count)
    {
        NativeCalls.godot_icall_1_38(MethodBind7, GodotObject.GetPtr(this), count);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetInputPortCount, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public int GetInputPortCount()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind8, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind9 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetInputPortName, 844755477ul);

    /// <summary>
    /// <para>Returns the name of the input port at the given <paramref name="id"/>.</para>
    /// </summary>
    public string GetInputPortName(int id)
    {
        string ret = NativeCalls.godot_icall_1_158(MethodBind9, GodotObject.GetPtr(this), id);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind10 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetInputPortType, 4102573379ul);

    /// <summary>
    /// <para>Returns the type of the input port at the given <paramref name="id"/>.</para>
    /// </summary>
    public VisualShaderNode.PortType GetInputPortType(int id)
    {
        VisualShaderNode.PortType ret = (VisualShaderNode.PortType)NativeCalls.godot_icall_1_85(MethodBind10, GodotObject.GetPtr(this), id);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind11 = ClassDB_get_method_with_compatibility(NativeName, MethodName.InsertOutputPort, 3880595796ul);

    /// <summary>
    /// <para>Inserts an output port at the given <paramref name="id"/> with the specified <paramref name="type"/> and <paramref name="name"/>.</para>
    /// <para>Returns the validated port name, which may differ from <paramref name="name"/> if a port with the same name already exists. Port names must be unique across both input and output ports.</para>
    /// </summary>
    public string InsertOutputPort(int id, VisualShaderNode.PortType type, string name)
    {
        string ret = NativeCalls.godot_icall_3_1557(MethodBind11, GodotObject.GetPtr(this), id, (int)type, name);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind12 = ClassDB_get_method_with_compatibility(NativeName, MethodName.RemoveOutputPort, 1286410249ul);

    /// <summary>
    /// <para>Removes the output port at the given <paramref name="id"/>.</para>
    /// </summary>
    public void RemoveOutputPort(int id)
    {
        NativeCalls.godot_icall_1_38(MethodBind12, GodotObject.GetPtr(this), id);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind13 = ClassDB_get_method_with_compatibility(NativeName, MethodName.MoveOutputPort, 3937882851ul);

    /// <summary>
    /// <para>Moves the output port at index <paramref name="from"/> to index <paramref name="to"/>. Connections to output nodes inside the group will be updated accordingly.</para>
    /// </summary>
    public void MoveOutputPort(int from, int to)
    {
        NativeCalls.godot_icall_2_84(MethodBind13, GodotObject.GetPtr(this), from, to);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind14 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetOutputPortName, 501894301ul);

    /// <summary>
    /// <para>Sets the name of the output port at the given <paramref name="id"/>.</para>
    /// </summary>
    public void SetOutputPortName(int id, string name)
    {
        NativeCalls.godot_icall_2_206(MethodBind14, GodotObject.GetPtr(this), id, name);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind15 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetOutputPortType, 1959648900ul);

    /// <summary>
    /// <para>Sets the type of the output port at the given <paramref name="id"/>.</para>
    /// </summary>
    public void SetOutputPortType(int id, VisualShaderNode.PortType type)
    {
        NativeCalls.godot_icall_2_84(MethodBind15, GodotObject.GetPtr(this), id, (int)type);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind16 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetOutputPortCount, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetOutputPortCount(int count)
    {
        NativeCalls.godot_icall_1_38(MethodBind16, GodotObject.GetPtr(this), count);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind17 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetOutputPortCount, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public int GetOutputPortCount()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind17, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind18 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetOutputPortName, 844755477ul);

    /// <summary>
    /// <para>Returns the name of the output port at the given <paramref name="id"/>.</para>
    /// </summary>
    public string GetOutputPortName(int id)
    {
        string ret = NativeCalls.godot_icall_1_158(MethodBind18, GodotObject.GetPtr(this), id);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind19 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetOutputPortType, 4102573379ul);

    /// <summary>
    /// <para>Returns the type of the output port at the given <paramref name="id"/>.</para>
    /// </summary>
    public VisualShaderNode.PortType GetOutputPortType(int id)
    {
        VisualShaderNode.PortType ret = (VisualShaderNode.PortType)NativeCalls.godot_icall_1_85(MethodBind19, GodotObject.GetPtr(this), id);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind20 = ClassDB_get_method_with_compatibility(NativeName, MethodName.AddNode, 3625527446ul);

    /// <summary>
    /// <para>Adds the specified <paramref name="node"/> to the group.</para>
    /// </summary>
    public unsafe void AddNode(VisualShaderNode node, Vector2 position, int id)
    {
        NativeCalls.godot_icall_3_178(MethodBind20, GodotObject.GetPtr(this), GodotObject.GetPtr(node), &position, id);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind21 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetNode, 1177927464ul);

    /// <summary>
    /// <para>Returns the shader node instance with the specified <paramref name="id"/>.</para>
    /// </summary>
    public VisualShaderNode GetNode(int id)
    {
        VisualShaderNode ret = (VisualShaderNode)NativeCalls.godot_icall_1_95(MethodBind21, GodotObject.GetPtr(this), id);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind22 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetNodePosition, 163021252ul);

    /// <summary>
    /// <para>Sets the position of the specified node.</para>
    /// </summary>
    public unsafe void SetNodePosition(int id, Vector2 position)
    {
        NativeCalls.godot_icall_2_175(MethodBind22, GodotObject.GetPtr(this), id, &position);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind23 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetNodePosition, 2299179447ul);

    /// <summary>
    /// <para>Returns the position of the specified node within the shader graph.</para>
    /// </summary>
    public Vector2 GetNodePosition(int id)
    {
        Vector2 ret = NativeCalls.godot_icall_1_176(MethodBind23, GodotObject.GetPtr(this), id);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind24 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetNodeList, 1930428628ul);

    /// <summary>
    /// <para>Returns the list of all nodes in the group.</para>
    /// </summary>
    public int[] GetNodeList()
    {
        int[] ret = NativeCalls.godot_icall_0_227(MethodBind24, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind25 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetValidNodeId, 3905245786ul);

    /// <summary>
    /// <para>Returns the next valid node ID that can be added to the shader graph.</para>
    /// </summary>
    public int GetValidNodeId()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind25, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind26 = ClassDB_get_method_with_compatibility(NativeName, MethodName.RemoveNode, 1286410249ul);

    /// <summary>
    /// <para>Removes the specified node from the group.</para>
    /// </summary>
    public void RemoveNode(int id)
    {
        NativeCalls.godot_icall_1_38(MethodBind26, GodotObject.GetPtr(this), id);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind27 = ClassDB_get_method_with_compatibility(NativeName, MethodName.ReplaceNode, 3780747571ul);

    /// <summary>
    /// <para>Replaces the specified node with a node of the new class type.</para>
    /// </summary>
    public void ReplaceNode(int id, StringName newClass)
    {
        NativeCalls.godot_icall_2_170(MethodBind27, GodotObject.GetPtr(this), id, (godot_string_name)(newClass?.NativeValue ?? default));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind28 = ClassDB_get_method_with_compatibility(NativeName, MethodName.IsNodeConnection, 1701679529ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if the specified node and port connection exists.</para>
    /// </summary>
    public bool IsNodeConnection(int fromNode, int fromPort, int toNode, int toPort)
    {
        bool ret = NativeCalls.godot_icall_4_1558(MethodBind28, GodotObject.GetPtr(this), fromNode, fromPort, toNode, toPort).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind29 = ClassDB_get_method_with_compatibility(NativeName, MethodName.CanConnectNodes, 1701679529ul);

    /// <summary>
    /// <para>Returns <see langword="true"/> if the specified nodes and ports can be connected.</para>
    /// </summary>
    public bool CanConnectNodes(int fromNode, int fromPort, int toNode, int toPort)
    {
        bool ret = NativeCalls.godot_icall_4_1558(MethodBind29, GodotObject.GetPtr(this), fromNode, fromPort, toNode, toPort).ToBool();
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind30 = ClassDB_get_method_with_compatibility(NativeName, MethodName.ConnectNodes, 3684568301ul);

    /// <summary>
    /// <para>Connects the specified nodes and ports.</para>
    /// </summary>
    public Error ConnectNodes(int fromNode, int fromPort, int toNode, int toPort)
    {
        Error ret = (Error)NativeCalls.godot_icall_4_469(MethodBind30, GodotObject.GetPtr(this), fromNode, fromPort, toNode, toPort);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind31 = ClassDB_get_method_with_compatibility(NativeName, MethodName.DisconnectNodes, 4275841770ul);

    /// <summary>
    /// <para>Disconnects the specified nodes and ports.</para>
    /// </summary>
    public void DisconnectNodes(int fromNode, int fromPort, int toNode, int toPort)
    {
        NativeCalls.godot_icall_4_177(MethodBind31, GodotObject.GetPtr(this), fromNode, fromPort, toNode, toPort);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind32 = ClassDB_get_method_with_compatibility(NativeName, MethodName.ConnectNodesForced, 4275841770ul);

    /// <summary>
    /// <para>Connects the specified nodes and ports, even if they can't be connected.</para>
    /// </summary>
    public void ConnectNodesForced(int fromNode, int fromPort, int toNode, int toPort)
    {
        NativeCalls.godot_icall_4_177(MethodBind32, GodotObject.GetPtr(this), fromNode, fromPort, toNode, toPort);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind33 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetNodeConnections, 3995934104ul);

    /// <summary>
    /// <para>Returns the list of connected nodes.</para>
    /// </summary>
    public Godot.Collections.Array<Godot.Collections.Dictionary> GetNodeConnections()
    {
        Godot.Collections.Array<Godot.Collections.Dictionary> ret = new Godot.Collections.Array<Godot.Collections.Dictionary>(NativeCalls.godot_icall_0_146(MethodBind33, GodotObject.GetPtr(this)));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind34 = ClassDB_get_method_with_compatibility(NativeName, MethodName.AttachNodeToFrame, 3937882851ul);

    /// <summary>
    /// <para>Attaches the given node to the given frame.</para>
    /// </summary>
    public void AttachNodeToFrame(int id, int frame)
    {
        NativeCalls.godot_icall_2_84(MethodBind34, GodotObject.GetPtr(this), id, frame);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind35 = ClassDB_get_method_with_compatibility(NativeName, MethodName.DetachNodeFromFrame, 1286410249ul);

    /// <summary>
    /// <para>Detaches the given node from the frame it is attached to.</para>
    /// </summary>
    public void DetachNodeFromFrame(int id)
    {
        NativeCalls.godot_icall_1_38(MethodBind35, GodotObject.GetPtr(this), id);
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
    public new class PropertyName : Resource.PropertyName
    {
        /// <summary>
        /// Cached name for the 'group_name' property.
        /// </summary>
        public static readonly StringName GroupName = "group_name";
        /// <summary>
        /// Cached name for the 'input_port_count' property.
        /// </summary>
        public static readonly StringName InputPortCount = "input_port_count";
        /// <summary>
        /// Cached name for the 'output_port_count' property.
        /// </summary>
        public static readonly StringName OutputPortCount = "output_port_count";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : Resource.MethodName
    {
        /// <summary>
        /// Cached name for the 'set_group_name' method.
        /// </summary>
        public static readonly StringName SetGroupName = "set_group_name";
        /// <summary>
        /// Cached name for the 'get_group_name' method.
        /// </summary>
        public static readonly StringName GetGroupName = "get_group_name";
        /// <summary>
        /// Cached name for the 'insert_input_port' method.
        /// </summary>
        public static readonly StringName InsertInputPort = "insert_input_port";
        /// <summary>
        /// Cached name for the 'remove_input_port' method.
        /// </summary>
        public static readonly StringName RemoveInputPort = "remove_input_port";
        /// <summary>
        /// Cached name for the 'move_input_port' method.
        /// </summary>
        public static readonly StringName MoveInputPort = "move_input_port";
        /// <summary>
        /// Cached name for the 'set_input_port_name' method.
        /// </summary>
        public static readonly StringName SetInputPortName = "set_input_port_name";
        /// <summary>
        /// Cached name for the 'set_input_port_type' method.
        /// </summary>
        public static readonly StringName SetInputPortType = "set_input_port_type";
        /// <summary>
        /// Cached name for the 'set_input_port_count' method.
        /// </summary>
        public static readonly StringName SetInputPortCount = "set_input_port_count";
        /// <summary>
        /// Cached name for the 'get_input_port_count' method.
        /// </summary>
        public static readonly StringName GetInputPortCount = "get_input_port_count";
        /// <summary>
        /// Cached name for the 'get_input_port_name' method.
        /// </summary>
        public static readonly StringName GetInputPortName = "get_input_port_name";
        /// <summary>
        /// Cached name for the 'get_input_port_type' method.
        /// </summary>
        public static readonly StringName GetInputPortType = "get_input_port_type";
        /// <summary>
        /// Cached name for the 'insert_output_port' method.
        /// </summary>
        public static readonly StringName InsertOutputPort = "insert_output_port";
        /// <summary>
        /// Cached name for the 'remove_output_port' method.
        /// </summary>
        public static readonly StringName RemoveOutputPort = "remove_output_port";
        /// <summary>
        /// Cached name for the 'move_output_port' method.
        /// </summary>
        public static readonly StringName MoveOutputPort = "move_output_port";
        /// <summary>
        /// Cached name for the 'set_output_port_name' method.
        /// </summary>
        public static readonly StringName SetOutputPortName = "set_output_port_name";
        /// <summary>
        /// Cached name for the 'set_output_port_type' method.
        /// </summary>
        public static readonly StringName SetOutputPortType = "set_output_port_type";
        /// <summary>
        /// Cached name for the 'set_output_port_count' method.
        /// </summary>
        public static readonly StringName SetOutputPortCount = "set_output_port_count";
        /// <summary>
        /// Cached name for the 'get_output_port_count' method.
        /// </summary>
        public static readonly StringName GetOutputPortCount = "get_output_port_count";
        /// <summary>
        /// Cached name for the 'get_output_port_name' method.
        /// </summary>
        public static readonly StringName GetOutputPortName = "get_output_port_name";
        /// <summary>
        /// Cached name for the 'get_output_port_type' method.
        /// </summary>
        public static readonly StringName GetOutputPortType = "get_output_port_type";
        /// <summary>
        /// Cached name for the 'add_node' method.
        /// </summary>
        public static readonly StringName AddNode = "add_node";
        /// <summary>
        /// Cached name for the 'get_node' method.
        /// </summary>
        public static readonly StringName GetNode = "get_node";
        /// <summary>
        /// Cached name for the 'set_node_position' method.
        /// </summary>
        public static readonly StringName SetNodePosition = "set_node_position";
        /// <summary>
        /// Cached name for the 'get_node_position' method.
        /// </summary>
        public static readonly StringName GetNodePosition = "get_node_position";
        /// <summary>
        /// Cached name for the 'get_node_list' method.
        /// </summary>
        public static readonly StringName GetNodeList = "get_node_list";
        /// <summary>
        /// Cached name for the 'get_valid_node_id' method.
        /// </summary>
        public static readonly StringName GetValidNodeId = "get_valid_node_id";
        /// <summary>
        /// Cached name for the 'remove_node' method.
        /// </summary>
        public static readonly StringName RemoveNode = "remove_node";
        /// <summary>
        /// Cached name for the 'replace_node' method.
        /// </summary>
        public static readonly StringName ReplaceNode = "replace_node";
        /// <summary>
        /// Cached name for the 'is_node_connection' method.
        /// </summary>
        public static readonly StringName IsNodeConnection = "is_node_connection";
        /// <summary>
        /// Cached name for the 'can_connect_nodes' method.
        /// </summary>
        public static readonly StringName CanConnectNodes = "can_connect_nodes";
        /// <summary>
        /// Cached name for the 'connect_nodes' method.
        /// </summary>
        public static readonly StringName ConnectNodes = "connect_nodes";
        /// <summary>
        /// Cached name for the 'disconnect_nodes' method.
        /// </summary>
        public static readonly StringName DisconnectNodes = "disconnect_nodes";
        /// <summary>
        /// Cached name for the 'connect_nodes_forced' method.
        /// </summary>
        public static readonly StringName ConnectNodesForced = "connect_nodes_forced";
        /// <summary>
        /// Cached name for the 'get_node_connections' method.
        /// </summary>
        public static readonly StringName GetNodeConnections = "get_node_connections";
        /// <summary>
        /// Cached name for the 'attach_node_to_frame' method.
        /// </summary>
        public static readonly StringName AttachNodeToFrame = "attach_node_to_frame";
        /// <summary>
        /// Cached name for the 'detach_node_from_frame' method.
        /// </summary>
        public static readonly StringName DetachNodeFromFrame = "detach_node_from_frame";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : Resource.SignalName
    {
    }
}
