package com.did.charactersheet.sync

import android.graphics.Typeface
import android.text.Html
import android.text.Spanned
import android.text.style.StyleSpan
import android.text.style.UnderlineSpan
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration

private const val DID_RICH_NOTE_MARKER = "<!--DID_RICH_NOTE-->"

/** Render the tiny rich-text subset emitted by the Windows DID app. */
fun didRichText(raw: String): AnnotatedString {
    if (raw.isBlank()) return AnnotatedString("")

    var source = raw
        .replace('\u2028', '\n')
        .replace('\u2029', '\n')
        .replace("\uFFFC", "")
        .replace("�", "")

    val containsHtml = source.startsWith(DID_RICH_NOTE_MARKER) ||
        Regex("<(?:/?(?:b|i|u|span)|br\\s*/?)\\b", RegexOption.IGNORE_CASE).containsMatchIn(source)

    if (!containsHtml) return AnnotatedString(source)

    source = source
        .removePrefix(DID_RICH_NOTE_MARKER)
        .replace("\n", "<br>")

    val spanned: Spanned = Html.fromHtml(source, Html.FROM_HTML_MODE_LEGACY)

    return buildAnnotatedString {
        append(spanned.toString().replace("\uFFFC", "").replace("�", ""))

        spanned.getSpans(0, spanned.length, StyleSpan::class.java).forEach { span ->
            val start = spanned.getSpanStart(span).coerceAtLeast(0)
            val end = spanned.getSpanEnd(span).coerceAtMost(length)
            if (start >= end) return@forEach
            val style = when (span.style) {
                Typeface.BOLD -> SpanStyle(fontWeight = FontWeight.Bold)
                Typeface.ITALIC -> SpanStyle(fontStyle = FontStyle.Italic)
                Typeface.BOLD_ITALIC -> SpanStyle(
                    fontWeight = FontWeight.Bold,
                    fontStyle = FontStyle.Italic,
                )
                else -> null
            }
            if (style != null) addStyle(style, start, end)
        }

        spanned.getSpans(0, spanned.length, UnderlineSpan::class.java).forEach { span ->
            val start = spanned.getSpanStart(span).coerceAtLeast(0)
            val end = spanned.getSpanEnd(span).coerceAtMost(length)
            if (start < end) {
                addStyle(SpanStyle(textDecoration = TextDecoration.Underline), start, end)
            }
        }
    }
}
