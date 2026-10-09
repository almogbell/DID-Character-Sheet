package com.did.charactersheet.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.Typography
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/**
 * Mobile interpretation of the finished Windows DID redesign.
 *
 * We deliberately use Android's built-in serif family rather than shipping a
 * font file. The desktop sheet uses Georgia heavily; the platform serif gives
 * the companion the same printed-character-sheet feel without bundling a font.
 */
object DidPalette {
    val Page = Color(0xFFFFFAF0)
    val Cream = Color(0xFFFFFDF7)
    val White = Color(0xFFFFFFFF)
    val Ink = Color(0xFF25190F)
    val MutedInk = Color(0xFF695B4D)
    val Gold = Color(0xFFCDAA63)
    val GoldLight = Color(0xFFD9BD82)
    val GoldDeep = Color(0xFFA87824)
    val Blue = Color(0xFFC7E6F7)
    val BlueSoft = Color(0xFFF4FBFF)
    val BlueStrong = Color(0xFF2F5F91)
    val Adversity = Color(0xFFD4AF37)
    val Heart = Color(0xFFC84A4A)
    val HeartEmpty = Color(0xFFF0D8D3)
    val Positive = Color(0xFF8FD694)
    val Negative = Color(0xFFF3A6A6)

    val DarkPage = Color(0xFF171410)
    val DarkCream = Color(0xFF211D18)
    val DarkSurface = Color(0xFF29231D)
    val DarkInk = Color(0xFFF6EAD2)
    val DarkMuted = Color(0xFFCDBFAE)
    val DarkGold = Color(0xFF8D7144)
    val DarkGoldLight = Color(0xFF6F5A39)
    val DarkBlue = Color(0xFF29485A)
}

private val DidLightColors = lightColorScheme(
    primary = DidPalette.BlueStrong,
    onPrimary = Color.White,
    primaryContainer = DidPalette.Blue,
    onPrimaryContainer = DidPalette.Ink,
    secondary = DidPalette.GoldDeep,
    onSecondary = Color.White,
    secondaryContainer = DidPalette.Cream,
    onSecondaryContainer = DidPalette.Ink,
    background = DidPalette.Page,
    onBackground = DidPalette.Ink,
    surface = DidPalette.Cream,
    onSurface = DidPalette.Ink,
    surfaceVariant = DidPalette.BlueSoft,
    onSurfaceVariant = DidPalette.MutedInk,
    outline = DidPalette.Gold,
    outlineVariant = DidPalette.GoldLight,
    error = Color(0xFFA90012),
)

private val DidDarkColors = darkColorScheme(
    primary = Color(0xFF9FD0EA),
    onPrimary = Color(0xFF102A39),
    primaryContainer = DidPalette.DarkBlue,
    onPrimaryContainer = DidPalette.DarkInk,
    secondary = Color(0xFFD8BA7D),
    onSecondary = Color(0xFF382A10),
    secondaryContainer = DidPalette.DarkSurface,
    onSecondaryContainer = DidPalette.DarkInk,
    background = DidPalette.DarkPage,
    onBackground = DidPalette.DarkInk,
    surface = DidPalette.DarkCream,
    onSurface = DidPalette.DarkInk,
    surfaceVariant = DidPalette.DarkSurface,
    onSurfaceVariant = DidPalette.DarkMuted,
    outline = DidPalette.DarkGold,
    outlineVariant = DidPalette.DarkGoldLight,
    error = Color(0xFFFF8B95),
)

private val DidTypography = Typography(
    displayLarge = TextStyle(fontFamily = FontFamily.Serif, fontWeight = FontWeight.Bold),
    displayMedium = TextStyle(fontFamily = FontFamily.Serif, fontWeight = FontWeight.Bold),
    displaySmall = TextStyle(fontFamily = FontFamily.Serif, fontWeight = FontWeight.Bold),
    headlineLarge = TextStyle(fontFamily = FontFamily.Serif, fontWeight = FontWeight.Bold),
    headlineMedium = TextStyle(fontFamily = FontFamily.Serif, fontWeight = FontWeight.Bold),
    headlineSmall = TextStyle(
        fontFamily = FontFamily.Serif,
        fontWeight = FontWeight.Black,
        fontSize = 24.sp,
    ),
    titleLarge = TextStyle(
        fontFamily = FontFamily.Serif,
        fontWeight = FontWeight.Black,
        fontSize = 21.sp,
    ),
    titleMedium = TextStyle(fontFamily = FontFamily.Serif, fontWeight = FontWeight.Bold),
    titleSmall = TextStyle(fontFamily = FontFamily.Serif, fontWeight = FontWeight.Bold),
    bodyLarge = TextStyle(fontFamily = FontFamily.Serif),
    bodyMedium = TextStyle(fontFamily = FontFamily.Serif),
    bodySmall = TextStyle(fontFamily = FontFamily.Serif),
    labelLarge = TextStyle(fontFamily = FontFamily.Serif, fontWeight = FontWeight.Bold),
    labelMedium = TextStyle(fontFamily = FontFamily.Serif, fontWeight = FontWeight.Bold),
    labelSmall = TextStyle(fontFamily = FontFamily.Serif),
)

@Composable
fun DidTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DidDarkColors else DidLightColors,
        typography = DidTypography,
        content = content,
    )
}
