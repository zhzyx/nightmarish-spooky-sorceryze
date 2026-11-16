"""Regression coverage for the event-gated late drain connection."""

import socket
import unittest

from RunM2DrainFaults import DrainConnectionGate


class DrainConnectionGateTests(unittest.TestCase):
    def test_buffers_connect_until_drain_event_and_forwards_both_directions(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                server.bind(("127.0.0.1", 0))
                client.bind(("127.0.0.1", 0))
                server.settimeout(0.05)
                client.settimeout(1)
                gate = DrainConnectionGate()
                self.addCleanup(gate.close)
                gate.set_server(server.getsockname()[1])
                client.sendto(b"prepared-connect", ("127.0.0.1", gate.port))
                self.assertTrue(gate.ready.wait(timeout=1))
                with self.assertRaises(socket.timeout):
                    server.recvfrom(1024)
                self.assertFalse(gate.released)
                self.assertEqual(gate.forwarded_client_packets, 0)
                gate.release()
                server.settimeout(1)
                payload, address = server.recvfrom(1024)
                self.assertEqual(payload, b"prepared-connect")
                self.assertTrue(gate.released)
                self.assertEqual(gate.forwarded_client_packets, 1)
                server.sendto(b"rejection-response", address)
                self.assertEqual(client.recvfrom(1024)[0], b"rejection-response")
                client.sendto(b"acknowledgement", ("127.0.0.1", gate.port))
                self.assertEqual(server.recvfrom(1024)[0], b"acknowledgement")
                self.assertEqual(gate.errors, [])

    def test_release_requires_a_prepared_client_and_server(self):
        gate = DrainConnectionGate()
        self.addCleanup(gate.close)
        gate.release()
        self.assertFalse(gate.released)
        self.assertEqual(gate.forwarded_client_packets, 0)
        self.assertEqual(gate.errors, ["Late client was not ready at the drain event"])


if __name__ == "__main__":
    unittest.main()
