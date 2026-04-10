import * as AuthSession from "expo-auth-session";
import * as Google from "expo-auth-session/providers/google";
import * as WebBrowser from "expo-web-browser";

// Required by expo-web-browser when returning from the OAuth redirect.
WebBrowser.maybeCompleteAuthSession();

const CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID ?? "";

/**
 * Hook that returns a `signIn` function plus reactive state.
 * Call this at the top of a React component:
 *
 *   const { signIn, ready } = useGoogleSignIn();
 *   ...
 *   <Button onPress={signIn} disabled={!ready} />
 */
export function useGoogleSignIn(): {
  signIn: () => Promise<string | null>;
  ready: boolean;
} {
  const [request, , promptAsync] = Google.useAuthRequest({
    clientId: CLIENT_ID,
    scopes: ["openid", "email", "profile"],
    // Use the Expo proxy so we don't need per-platform redirect config.
    redirectUri: AuthSession.makeRedirectUri({ useProxy: true } as any),
  });

  const signIn = async (): Promise<string | null> => {
    if (!request) return null;
    const result = await promptAsync({ useProxy: true } as any);
    if (result?.type !== "success") return null;
    // The ID token is in result.params.id_token for the Google provider.
    const idToken = (result.params as { id_token?: string }).id_token;
    return idToken ?? null;
  };

  return { signIn, ready: request !== null };
}
