package com.taalbrug.app

import android.graphics.Color as AndroidColor
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import com.taalbrug.app.ui.DarkPalette
import com.taalbrug.app.ui.LightPalette
import com.taalbrug.app.ui.MainMenuScreen
import com.taalbrug.app.ui.ManageScreen
import com.taalbrug.app.ui.ModeSelectScreen
import com.taalbrug.app.ui.StatisticsScreen
import com.taalbrug.app.ui.TaalbrugTheme
import com.taalbrug.app.ui.TrainingScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!Store.isReady) {
            Store.init(this)
            if (savedInstanceState == null) Store.logActivity("app_start")
        }

        setContent {
            // the theme is stored in the settings table like on the desktop; without a choice, follow the phone
            val systemDark = isSystemInDarkTheme()
            var dark by remember { mutableStateOf(Store.loadSetting("theme")?.let { it == "dark" } ?: systemDark) }
            LaunchedEffect(dark) {
                val transparent = AndroidColor.TRANSPARENT
                val style = if (dark) SystemBarStyle.dark(transparent) else SystemBarStyle.light(transparent, transparent)
                enableEdgeToEdge(statusBarStyle = style, navigationBarStyle = style)
            }

            // screens: "menu", "modes", "train/<mode>", "stats", "manage"
            var route by rememberSaveable { mutableStateOf("menu") }
            BackHandler(enabled = route != "menu") {
                route = if (route.startsWith("train/")) "modes" else "menu"
            }

            val palette = if (dark) DarkPalette else LightPalette
            TaalbrugTheme(palette) {
                Box(Modifier.fillMaxSize().background(palette.bg).safeDrawingPadding()) {
                    when {
                        route == "menu" -> MainMenuScreen(
                            dark = dark,
                            onNavigate = { route = it },
                            onToggleTheme = {
                                dark = !dark
                                Store.saveSetting("theme", if (dark) "dark" else "light")
                            },
                        )
                        route == "modes" -> ModeSelectScreen(onStart = { route = "train/${it.code}" }, onBack = { route = "menu" })
                        route.startsWith("train/") -> TrainingScreen(Mode.valueOf(route.removePrefix("train/")), onEnd = { route = "menu" })
                        route == "stats" -> StatisticsScreen(onBack = { route = "menu" })
                        route == "manage" -> ManageScreen(onBack = { route = "menu" })
                    }
                }
            }
        }
    }
}
