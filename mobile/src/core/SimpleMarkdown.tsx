import React from "react";
import { StyleSheet, Text, View } from "react-native";

/**
 * Minimal markdown renderer. Supports:
 *   # / ## / ###  — headers
 *   -             — bullet lists
 *   **bold**      — inline bold
 *   blank lines   — paragraph breaks
 *
 * Anything else renders as plain text. Good enough for short plugin
 * help docs; swap for react-native-markdown-display if we ever need
 * tables, code blocks, or links.
 */
export function SimpleMarkdown({ source }: { source: string }) {
  const lines = source.split(/\r?\n/);
  const blocks: React.ReactNode[] = [];
  let paragraph: string[] = [];
  let bullets: string[] = [];

  const flushPara = (key: string) => {
    if (paragraph.length) {
      blocks.push(
        <Text key={`p-${key}`} style={styles.para}>
          {renderInline(paragraph.join(" "))}
        </Text>,
      );
      paragraph = [];
    }
  };

  const flushBullets = (key: string) => {
    if (bullets.length) {
      blocks.push(
        <View key={`ul-${key}`} style={styles.ul}>
          {bullets.map((b, i) => (
            <View key={i} style={styles.li}>
              <Text style={styles.bullet}>•</Text>
              <Text style={styles.liText}>{renderInline(b)}</Text>
            </View>
          ))}
        </View>,
      );
      bullets = [];
    }
  };

  lines.forEach((raw, i) => {
    const line = raw.trim();
    const key = String(i);
    if (!line) {
      flushPara(key);
      flushBullets(key);
      return;
    }
    if (line.startsWith("### ")) {
      flushPara(key); flushBullets(key);
      blocks.push(<Text key={`h3-${key}`} style={styles.h3}>{line.slice(4)}</Text>);
    } else if (line.startsWith("## ")) {
      flushPara(key); flushBullets(key);
      blocks.push(<Text key={`h2-${key}`} style={styles.h2}>{line.slice(3)}</Text>);
    } else if (line.startsWith("# ")) {
      flushPara(key); flushBullets(key);
      blocks.push(<Text key={`h1-${key}`} style={styles.h1}>{line.slice(2)}</Text>);
    } else if (line.startsWith("- ")) {
      flushPara(key);
      bullets.push(line.slice(2));
    } else {
      flushBullets(key);
      paragraph.push(line);
    }
  });
  flushPara("end");
  flushBullets("end");

  return <View>{blocks}</View>;
}

function renderInline(text: string): React.ReactNode {
  // Split on **bold** spans
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**")) {
      return <Text key={i} style={styles.bold}>{p.slice(2, -2)}</Text>;
    }
    return <Text key={i}>{p}</Text>;
  });
}

const styles = StyleSheet.create({
  h1: { fontSize: 22, fontWeight: "700", marginTop: 16, marginBottom: 8, color: "#0f172a" },
  h2: { fontSize: 18, fontWeight: "700", marginTop: 14, marginBottom: 6, color: "#0f172a" },
  h3: { fontSize: 15, fontWeight: "700", marginTop: 10, marginBottom: 4, color: "#334155" },
  para: { fontSize: 14, lineHeight: 21, color: "#1f2937", marginBottom: 8 },
  ul: { marginBottom: 8 },
  li: { flexDirection: "row", marginBottom: 4, paddingLeft: 4 },
  bullet: { width: 14, color: "#64748b", fontSize: 14, lineHeight: 21 },
  liText: { flex: 1, fontSize: 14, lineHeight: 21, color: "#1f2937" },
  bold: { fontWeight: "700" },
});
