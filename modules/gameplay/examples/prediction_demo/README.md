# Gameplay prediction integration demo

This headless sample composes the GF-1 gameplay types, GF-2 ENet session and stable PlayerState identity, GF-3 property replication, GF-4 replication graph relevancy, and GF-5 owner prediction/remote interpolation. Build the editor with `tests=yes` from the repository root, then open three PowerShell terminals.

```powershell
./bin/godot.windows.editor.x86_64.console.exe --headless --path ./modules/gameplay/examples/prediction_demo -- --role=server --port=7200 --latency-ms=18 --jitter-ms=7 --loss-permyriad=1500
./bin/godot.windows.editor.x86_64.console.exe --headless --path ./modules/gameplay/examples/prediction_demo -- --role=client --port=7200 --user=alice --latency-ms=18 --jitter-ms=7 --loss-permyriad=1500
./bin/godot.windows.editor.x86_64.console.exe --headless --path ./modules/gameplay/examples/prediction_demo -- --role=client --port=7200 --user=bob --latency-ms=18 --jitter-ms=7 --loss-permyriad=1500
```

Each client prints its immediately predicted owner position, last server-confirmed sequence, bounded pending input count, and the other player's delayed interpolation sample. The server prints the stable PlayerState instance used for each spawn.

To exercise reconnect, stop Alice while leaving the server and Bob running, wait for the server to observe the disconnect, then start Alice again with the deterministic demo credential. For a scripted clean disconnect, add `--exit-after=5` to Alice's first command.

```powershell
./bin/godot.windows.editor.x86_64.console.exe --headless --path ./modules/gameplay/examples/prediction_demo -- --role=client --port=7200 --user=alice --reconnect=resume-alice --latency-ms=18 --jitter-ms=7 --loss-permyriad=1500
```

The server reports the old and new peer IDs and the unchanged PlayerState instance. The reconnecting predictor accepts the server's newer confirmation as its baseline, advances its input sequence, and resumes prediction. These credentials and the application-layer network conditions are for a local reproducible sample only; ENet does not encrypt credentials.

For a non-interactive regression covering the same topology, authority rejection, loss convergence, relevancy, interpolation, and reconnect identity, run:

```powershell
./bin/godot.windows.editor.x86_64.console.exe --headless --test --test-case="*Gameplay*" --no-colors
```
