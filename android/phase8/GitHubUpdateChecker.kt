package com.did.charactersheet.update

import android.os.Handler
import android.os.Looper
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

/** Reads and validates the Android update manifest from the DID GitHub repository. */
class GitHubUpdateChecker(
    private val currentVersion: String,
    private val manifestUrl: String = DEFAULT_MANIFEST_URL,
) {
    data class UpdateInfo(
        val version: String,
        val minimumDesktopVersion: String?,
        val syncProtocol: Int,
        val downloadUrl: String?,
        val releaseUrl: String?,
        val releaseNotes: String?,
    )

    private val executor = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())

    fun check(callback: (Result<UpdateInfo?>) -> Unit) {
        executor.execute {
            val result = runCatching {
                val connection = (URL(manifestUrl).openConnection() as HttpURLConnection).apply {
                    connectTimeout = 7000
                    readTimeout = 7000
                    requestMethod = "GET"
                    setRequestProperty("Accept", "application/json")
                    setRequestProperty("Cache-Control", "no-cache")
                    setRequestProperty("User-Agent", "DID-Character-Sheet-Android/$currentVersion")
                }
                try {
                    if (connection.responseCode !in 200..299) {
                        error("Update server returned HTTP ${connection.responseCode}")
                    }
                    val text = connection.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
                    val json = JSONObject(text)
                    require(json.optString("platform") == "android") {
                        "The update manifest is not for the Android app."
                    }
                    val available = json.getString("version").trim()
                    require(available.matches(Regex("\\d+\\.\\d+\\.\\d+(?:[-+][0-9A-Za-z.-]+)?"))) {
                        "The update manifest has an invalid Android version."
                    }
                    val protocol = json.getInt("sync_protocol")
                    require(protocol > 0) { "The update manifest has an invalid sync protocol." }

                    if (compareVersions(available, currentVersion) <= 0) {
                        null
                    } else {
                        UpdateInfo(
                            version = available,
                            minimumDesktopVersion = json.optString("minimum_desktop_version").ifBlank { null },
                            syncProtocol = protocol,
                            downloadUrl = json.optString("download_url").ifBlank { null },
                            releaseUrl = json.optString("release_url").ifBlank { null },
                            releaseNotes = json.optString("release_notes").ifBlank { null },
                        )
                    }
                } finally {
                    connection.disconnect()
                }
            }
            main.post { callback(result) }
        }
    }

    companion object {
        const val DEFAULT_MANIFEST_URL =
            "https://raw.githubusercontent.com/almogbell/DID-Character-Sheet/main/updates/android.json"

        internal fun compareVersions(a: String, b: String): Int {
            val left = a.trim().removePrefix("v").split('.')
            val right = b.trim().removePrefix("v").split('.')
            val max = maxOf(left.size, right.size)
            for (i in 0 until max) {
                val x = left.getOrNull(i)?.takeWhile { it.isDigit() }?.toIntOrNull() ?: 0
                val y = right.getOrNull(i)?.takeWhile { it.isDigit() }?.toIntOrNull() ?: 0
                if (x != y) return x.compareTo(y)
            }
            return 0
        }
    }
}
