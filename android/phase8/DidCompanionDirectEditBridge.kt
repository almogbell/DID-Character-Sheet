package com.did.charactersheet.sync

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

/**
 * Phase 9 compatibility overload.
 *
 * The desktop command paths for name/backstory/inventory are now available and
 * are threaded through the Activity/ViewModel/root. The visual sheet remains
 * focused on parity in this increment; dedicated edit dialogs can consume these
 * callbacks without changing the network contract again.
 */
@Composable
fun DidCompanionSheet(
    snapshot: DidCharacterSnapshot,
    connected: Boolean,
    pending: Boolean,
    onHpChange: (Int) -> Unit,
    onAtChange: (Int) -> Unit,
    onIpChange: (Int) -> Unit,
    onSetName: (String) -> Unit,
    onSetBackstory: (String) -> Unit,
    onAddInventoryItem: (String, String, Int) -> Unit,
    onUpdateInventoryItem: (String, String, String, Int) -> Unit,
    onRemoveInventoryItem: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    // Keep these strongly typed through the UI layer now, even before the edit
    // affordances are promoted into the desktop-parity layout.
    @Suppress("UNUSED_VARIABLE")
    val directEditCommands = arrayOf<Any>(
        onSetName,
        onSetBackstory,
        onAddInventoryItem,
        onUpdateInventoryItem,
        onRemoveInventoryItem,
    )

    DidCompanionSheet(
        snapshot = snapshot,
        connected = connected,
        pending = pending,
        onHpChange = onHpChange,
        onAtChange = onAtChange,
        onIpChange = onIpChange,
        modifier = modifier,
    )
}
