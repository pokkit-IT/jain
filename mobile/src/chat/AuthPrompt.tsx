import React, { useState } from "react";
import { Alert, StyleSheet, Text, TouchableOpacity, View } from "react-native";

import { signInWithGoogle } from "../api/auth";
import { useGoogleSignIn } from "../auth/googleAuth";
import { setToken } from "../auth/tokenStorage";
import { useAppStore } from "../store/useAppStore";

interface AuthPromptProps {
  /**
   * Called after sign-in completes successfully (session is set, token
   * stored). Use this to trigger the pending message retry directly
   * from the chat screen, avoiding a useEffect closure timing race.
   */
  onSignInComplete?: () => void;
}

/**
 * Inline login prompt shown in the chat when the backend returns
 * display_hint === "auth_required". Uses the same Google OAuth flow
 * as the Settings tab.
 */
export function AuthPrompt({ onSignInComplete }: AuthPromptProps) {
  const setSession = useAppStore((s) => s.setSession);
  const clearPendingRetry = useAppStore((s) => s.clearPendingRetry);
  const { signIn: googleSignIn, ready: googleReady } = useGoogleSignIn();
  const [signingIn, setSigningIn] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  const handleSignIn = async () => {
    if (signingIn) return;
    setSigningIn(true);
    try {
      console.log("[AuthPrompt] starting Google sign-in");
      const idToken = await googleSignIn();
      if (!idToken) {
        console.log("[AuthPrompt] no idToken (user cancelled?)");
        return;
      }
      console.log("[AuthPrompt] exchanging idToken at /api/auth/google");
      const newSession = await signInWithGoogle(idToken);
      await setToken(newSession.token);
      setSession(newSession);
      console.log("[AuthPrompt] session set, dismissing prompt + triggering retry");
      // Dismiss ourselves so the AuthPrompt disappears even if parent
      // re-renders are slow / if the retry fails.
      setDismissed(true);
      // Directly trigger the retry via the callback passed from
      // ChatScreen. This avoids depending on a useEffect closure that
      // captures stale `send` / `messages` state.
      onSignInComplete?.();
    } catch (e) {
      console.log("[AuthPrompt] sign-in error:", (e as Error).message);
      Alert.alert("Sign-in failed", (e as Error).message || "Try again later.");
    } finally {
      setSigningIn(false);
    }
  };

  const handleDismiss = () => {
    clearPendingRetry();
    setDismissed(true);
  };

  return (
    <View style={styles.card}>
      <TouchableOpacity style={styles.dismiss} onPress={handleDismiss}>
        <Text style={styles.dismissText}>×</Text>
      </TouchableOpacity>

      <Text style={styles.title}>Sign in to continue</Text>
      <Text style={styles.subtitle}>
        You'll need to sign in with Google to continue with that request.
      </Text>

      <TouchableOpacity
        style={[
          styles.button,
          (!googleReady || signingIn) && styles.buttonDisabled,
        ]}
        onPress={handleSignIn}
        disabled={!googleReady || signingIn}
      >
        <Text style={styles.buttonText}>
          {signingIn ? "Signing in..." : "Sign in with Google"}
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#eff6ff",
    padding: 16,
    marginHorizontal: 12,
    marginVertical: 8,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#bfdbfe",
    position: "relative",
  },
  dismiss: {
    position: "absolute",
    top: 6,
    right: 10,
    width: 24,
    height: 24,
    alignItems: "center",
    justifyContent: "center",
  },
  dismissText: {
    fontSize: 22,
    color: "#64748b",
    lineHeight: 22,
  },
  title: {
    fontSize: 16,
    fontWeight: "600",
    color: "#1e3a8a",
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 14,
    color: "#1e40af",
    marginBottom: 12,
  },
  button: {
    backgroundColor: "#2563eb",
    padding: 12,
    borderRadius: 8,
    alignItems: "center",
  },
  buttonDisabled: {
    backgroundColor: "#94a3b8",
  },
  buttonText: {
    color: "#fff",
    fontSize: 15,
    fontWeight: "600",
  },
});
