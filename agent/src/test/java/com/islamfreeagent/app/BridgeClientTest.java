package com.islamfreeagent.app;

import org.junit.Test;

import static org.junit.Assert.*;

public class BridgeClientTest {
    @Test public void acceptsPrivateLanIpv4Addresses() {
        assertTrue(BridgeClient.isPrivateIpv4("192.168.1.5"));
        assertTrue(BridgeClient.isPrivateIpv4("10.0.0.2"));
        assertTrue(BridgeClient.isPrivateIpv4("172.16.0.4"));
    }

    @Test public void rejectsPublicLoopbackAndInvalidHosts() {
        assertFalse(BridgeClient.isPrivateIpv4("8.8.8.8"));
        assertFalse(BridgeClient.isPrivateIpv4("1.1.1.1"));
        assertFalse(BridgeClient.isPrivateIpv4("127.0.0.1"));
        assertFalse(BridgeClient.isPrivateIpv4("localhost"));
        assertFalse(BridgeClient.isPrivateIpv4("192.168.1.999"));
        assertFalse(BridgeClient.isPrivateIpv4("0.0.0.0"));
    }
}
