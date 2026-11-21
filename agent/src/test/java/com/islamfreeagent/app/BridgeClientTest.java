package com.islamfreeagent.app;

import org.junit.Test;

import static org.junit.Assert.*;

public class BridgeClientTest {
    @Test public void acceptsPrivateLanIpv4Addresses() {
        assertTrue(BridgeClient.isPrivateIpv4("192.168.1.5"));
        assertTrue(BridgeClient.isPrivateIpv4("10.0.0.2"));
        assertTrue(BridgeClient.isPrivateIpv4("172.16.0.4"));
    }

    @Test public void acceptsTailscaleOverlayAddresses() {
        assertTrue(BridgeClient.isAllowedBridgeIpv4("100.64.0.1"));
        assertTrue(BridgeClient.isAllowedBridgeIpv4("100.100.20.30"));
        assertTrue(BridgeClient.isAllowedBridgeIpv4("100.127.255.254"));
    }

    @Test public void rejectsAddressesOutsideLanAndTailscaleRanges() {
        assertFalse(BridgeClient.isAllowedBridgeIpv4("100.63.255.255"));
        assertFalse(BridgeClient.isAllowedBridgeIpv4("100.128.0.1"));
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
