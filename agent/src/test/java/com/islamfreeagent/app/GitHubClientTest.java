package com.islamfreeagent.app;

import org.junit.Test;
import static org.junit.Assert.*;

public class GitHubClientTest {
    @Test public void rejectsEmptyOrShortTokens() {
        try { new GitHubClient(""); fail("empty token must fail"); }
        catch (IllegalArgumentException expected) { }
        try { new GitHubClient("short"); fail("short token must fail"); }
        catch (IllegalArgumentException expected) { }
    }

    @Test public void rejectsMultilineTokens() {
        try { new GitHubClient("github_pat_valid-looking-token-123456789\nInjected: yes"); fail("newline must fail"); }
        catch (IllegalArgumentException expected) { }
    }

    @Test public void remoteWriteFailsClosedBeforeAnyNetworkRequest() throws Exception {
        GitHubClient client = new GitHubClient("github_pat_example_valid_length_1234567890");
        try {
            client.commitApprovedFile("docs/agent/agent_worklog.md", "approved text", "test");
            fail("remote write must remain disabled");
        } catch (SecurityException expected) {
            assertTrue(expected.getMessage().contains("معطل"));
        }
    }

    @Test public void writeAllowlistContainsOnlyApprovedProjectFiles() {
        assertFalse(GitHubClient.isAllowedWritePath("agent/src/main/java/com/islamfreeagent/app/MainActivity.java"));
        assertTrue(GitHubClient.isAllowedWritePath("docs/agent/agent_worklog.md"));
        assertFalse(GitHubClient.isAllowedWritePath(".github/workflows/release.yml"));
        assertFalse(GitHubClient.isAllowedWritePath("docs/agent/agent_memory.json"));
        assertFalse(GitHubClient.isAllowedWritePath("agent/src/main/java/com/islamfreeagent/app/GitHubClient.java"));
        assertFalse(GitHubClient.isAllowedWritePath("agent/src/main/java/com/islamfreeagent/app/BridgeClient.java"));
        assertFalse(GitHubClient.isAllowedWritePath("../../.env"));
        assertFalse(GitHubClient.isAllowedWritePath(null));
    }

    @Test public void acceptsOpaqueFineGrainedToken() {
        GitHubClient client = new GitHubClient("github_pat_example_valid_length_1234567890");
        assertNotNull(client);
    }
}
