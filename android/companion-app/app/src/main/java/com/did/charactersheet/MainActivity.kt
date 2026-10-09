package com.did.charactersheet

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import com.did.charactersheet.sync.DidCompanionApp
import com.did.charactersheet.sync.DidCompanionViewModel
import com.did.charactersheet.sync.PairingScanner

class MainActivity : ComponentActivity() {
    private val companionViewModel: DidCompanionViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val pairingScanner = PairingScanner(this)

        setContent {
            DidCompanionApp(
                viewModel = companionViewModel,
                requestQrScan = { onScanned, onError ->
                    pairingScanner.start(this) { result ->
                        when (result) {
                            is PairingScanner.Result.Success -> onScanned(result.rawJson)
                            is PairingScanner.Result.Error -> onError(result.message)
                            PairingScanner.Result.Cancelled -> Unit
                        }
                    }
                },
            )
        }
    }
}
