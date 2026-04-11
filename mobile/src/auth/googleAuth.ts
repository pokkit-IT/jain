import { ResponseType } from "expo-auth-session";
import * as Google from "expo-auth-session/providers/google";
import * as WebBrowser from "expo-web-browser";

// Required by expo-web-browser when returning from the OAuth redirect.
WebBrowser.maybeCompleteAuthSession();

// Platform-specific client IDs from Google Cloud Console.
// - iOS client uses Bundle ID `host.exp.Exponent` (Expo Go's native bundle)
// - Android client uses package `host.exp.exponent` + Expo Go SHA-1
// - Web client uses `https://auth.expo.io/...` redirect (or localhost)
// expo-auth-session picks the right one based on Platform.OS at runtime.
const IOS_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID ?? "";
const ANDROID_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID ?? "";
const WEB_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID ?? "";

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
    iosClientId: IOS_CLIENT_ID || undefined,
    androidClientId: ANDROID_CLIENT_ID || undefined,
    webClientId: WEB_CLIENT_ID || undefined,
    scopes: ["openid", "email", "profile"],
    // Request an OIDC ID token (JWT) — our backend verifies this against
    // Google's public keys. The default (Token) only returns an access_token
    // for calling Google APIs, which isn't useful for identity.
    responseType: ResponseType.IdToken,
    // Force Google to show the account picker. Without this, Google
    // auto-approves the request if the user already has an active session,
    // redirecting the popup so fast that Chrome's Cross-Origin-Opener-Policy
    // prevents expo-web-browser from detecting the close event. The account
    // picker keeps the popup open long enough for the result to propagate.
    extraParams: {
      prompt: "select_account",
    },
  });

  const signIn = async (): Promise<string | null> => {
    if (!request) return null;
    const result = await promptAsync();
    if (result?.type !== "success") return null;
    // The ID token is in result.params.id_token for the Google provider.
    const idToken = (result.params as { id_token?: string }).id_token;
    return idToken ?? null;
  };

  return { signIn, ready: request !== null };
}
