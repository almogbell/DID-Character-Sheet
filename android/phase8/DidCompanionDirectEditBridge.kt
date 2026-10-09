package com.did.charactersheet.sync

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp

/**
 * Phase 9 direct-edit shell around the desktop-parity character sheet.
 *
 * Each editor submits exactly one authoritative Windows command at a time. No
 * local character copy is modified optimistically.
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
    var editName by remember { mutableStateOf(false) }
    var editBackstory by remember { mutableStateOf(false) }
    var manageInventory by remember { mutableStateOf(false) }
    val canEdit = connected && !pending

    Column(modifier) {
        Surface(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 2.dp),
            shape = RoundedCornerShape(10.dp),
            color = MaterialTheme.colorScheme.surface,
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
        ) {
            Row(
                Modifier.fillMaxWidth().padding(6.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                OutlinedButton(
                    onClick = { editName = true },
                    enabled = canEdit,
                    modifier = Modifier.weight(1f),
                ) { Text("Name") }
                OutlinedButton(
                    onClick = { editBackstory = true },
                    enabled = canEdit,
                    modifier = Modifier.weight(1f),
                ) { Text("Backstory") }
                OutlinedButton(
                    onClick = { manageInventory = true },
                    enabled = canEdit,
                    modifier = Modifier.weight(1f),
                ) { Text("Inventory") }
            }
        }

        DidCompanionSheet(
            snapshot = snapshot,
            connected = connected,
            pending = pending,
            onHpChange = onHpChange,
            onAtChange = onAtChange,
            onIpChange = onIpChange,
            modifier = Modifier.weight(1f),
        )
    }

    if (editName) {
        SingleTextEditDialog(
            title = "Character name",
            initial = snapshot.name,
            multiline = false,
            onDismiss = { editName = false },
            onSave = {
                onSetName(it)
                editName = false
            },
        )
    }

    if (editBackstory) {
        SingleTextEditDialog(
            title = "Backstory",
            initial = snapshot.backstory,
            multiline = true,
            onDismiss = { editBackstory = false },
            onSave = {
                onSetBackstory(it)
                editBackstory = false
            },
        )
    }

    if (manageInventory) {
        InventoryManagerDialog(
            items = snapshot.inventory,
            onDismiss = { manageInventory = false },
            onAdd = { name, description, quantity ->
                onAddInventoryItem(name, description, quantity)
                manageInventory = false
            },
            onUpdate = { id, name, description, quantity ->
                onUpdateInventoryItem(id, name, description, quantity)
                manageInventory = false
            },
            onRemove = { id ->
                onRemoveInventoryItem(id)
                manageInventory = false
            },
        )
    }
}

@Composable
private fun SingleTextEditDialog(
    title: String,
    initial: String,
    multiline: Boolean,
    onDismiss: () -> Unit,
    onSave: (String) -> Unit,
) {
    var value by remember(initial) { mutableStateOf(initial) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title, fontWeight = FontWeight.Black) },
        text = {
            OutlinedTextField(
                value = value,
                onValueChange = { value = it },
                modifier = Modifier.fillMaxWidth(),
                singleLine = !multiline,
                minLines = if (multiline) 5 else 1,
                maxLines = if (multiline) 12 else 1,
            )
        },
        confirmButton = {
            Button(onClick = { onSave(value) }) { Text("Save") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        },
    )
}

@Composable
private fun InventoryManagerDialog(
    items: List<InventoryItemSnapshot>,
    onDismiss: () -> Unit,
    onAdd: (String, String, Int) -> Unit,
    onUpdate: (String, String, String, Int) -> Unit,
    onRemove: (String) -> Unit,
) {
    var editing by remember { mutableStateOf<InventoryItemSnapshot?>(null) }
    var adding by remember { mutableStateOf(false) }

    if (adding || editing != null) {
        InventoryItemEditDialog(
            item = editing,
            onDismiss = {
                adding = false
                editing = null
            },
            onSave = { name, description, quantity ->
                val item = editing
                if (item?.id != null) {
                    onUpdate(item.id, name, description, quantity)
                } else {
                    onAdd(name, description, quantity)
                }
            },
            onRemove = editing?.id?.let { id -> { onRemove(id) } },
        )
        return
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Inventory", fontWeight = FontWeight.Black) },
        text = {
            if (items.isEmpty()) {
                Text("No items yet.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                LazyColumn(
                    Modifier.fillMaxWidth().heightIn(max = 430.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    items(items, key = { it.id ?: "${it.name}:${it.quantity}" }) { item ->
                        Surface(
                            modifier = Modifier.fillMaxWidth().clickable { editing = item },
                            shape = RoundedCornerShape(9.dp),
                            color = MaterialTheme.colorScheme.secondaryContainer,
                            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                        ) {
                            Row(
                                Modifier.fillMaxWidth().padding(10.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Column(Modifier.weight(1f)) {
                                    Text(item.name.ifBlank { "Unnamed item" }, fontWeight = FontWeight.Black)
                                    if (item.description.isNotBlank()) {
                                        Text(
                                            item.description,
                                            style = MaterialTheme.typography.bodySmall,
                                            maxLines = 2,
                                        )
                                    }
                                }
                                Text("×${item.quantity}", fontWeight = FontWeight.Black)
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            Button(onClick = { adding = true }) { Text("+ Add item") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Close") }
        },
    )
}

@Composable
private fun InventoryItemEditDialog(
    item: InventoryItemSnapshot?,
    onDismiss: () -> Unit,
    onSave: (String, String, Int) -> Unit,
    onRemove: (() -> Unit)?,
) {
    var name by remember(item?.id) { mutableStateOf(item?.name.orEmpty()) }
    var description by remember(item?.id) { mutableStateOf(item?.description.orEmpty()) }
    var quantity by remember(item?.id) { mutableStateOf((item?.quantity ?: 1).toString()) }
    var confirmDelete by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Text(
                if (item == null) "Add inventory item" else "Edit inventory item",
                fontWeight = FontWeight.Black,
            )
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Name") },
                    singleLine = true,
                )
                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Description") },
                    minLines = 3,
                    maxLines = 8,
                )
                OutlinedTextField(
                    value = quantity,
                    onValueChange = { if (it.all(Char::isDigit)) quantity = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Quantity") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true,
                )
            }
        },
        confirmButton = {
            Button(
                enabled = quantity.toIntOrNull() != null,
                onClick = { onSave(name, description, quantity.toIntOrNull() ?: 0) },
            ) { Text("Save") }
        },
        dismissButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                if (onRemove != null) {
                    TextButton(onClick = { confirmDelete = true }) {
                        Text("Delete", color = MaterialTheme.colorScheme.error)
                    }
                }
                TextButton(onClick = onDismiss) { Text("Cancel") }
            }
        },
    )

    if (confirmDelete && onRemove != null) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("Delete item?") },
            text = { Text("This removes the item from the Windows character too.") },
            confirmButton = {
                Button(
                    onClick = onRemove,
                    colors = androidx.compose.material3.ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.error,
                    ),
                ) { Text("Delete") }
            },
            dismissButton = {
                TextButton(onClick = { confirmDelete = false }) { Text("Cancel") }
            },
        )
    }
}
