package com.rookiedev.hexapod

import android.annotation.SuppressLint
import android.content.res.Resources
import android.os.Bundle
import android.util.TypedValue
import android.view.*
import android.widget.ImageView
import androidx.appcompat.app.AppCompatActivity
import com.rookiedev.hexapod.network.TCPClient
import com.rookiedev.hexapod.network.TCPClient.OnConnectEstablished
import com.rookiedev.hexapod.network.TCPClient.OnMessageReceived
import java.util.concurrent.locks.ReentrantLock
import kotlin.math.PI
import kotlin.math.atan2
import kotlin.math.pow
import kotlin.math.sqrt
import kotlinx.coroutines.*


/**
 * Behaviors of immersive mode.
 */
enum class BehaviorOption(
    val title: String,
    val value: Int
) {
    // Swipe from the edge to show a hidden bar. Gesture navigation works regardless of visibility
    // of the navigation bar.
    Default(
        "BEHAVIOR_DEFAULT",
        WindowInsetsController.BEHAVIOR_DEFAULT
    ),

    // "Sticky immersive mode". Swipe from the edge to temporarily reveal the hidden bar.
    ShowTransientBarsBySwipe(
        "BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE",
        WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
    )
}

/**
 * Type of system bars to hide or show.
 */
enum class TypeOption(
    val title: String,
    val value: Int
) {
    // Both the status bar and the navigation bar
    SystemBars(
        "systemBars()",
        WindowInsets.Type.systemBars()
    ),

    // The status bar only.
    StatusBar(
        "statusBars()",
        WindowInsets.Type.statusBars()
    ),

    // The navigation bar only
    NavigationBar(
        "navigationBars()",
        WindowInsets.Type.navigationBars()
    )
}

class ControlActivity : AppCompatActivity() {
    private var pxMargin = 0f
    private var width = 0
    private var height = 0
    private var radius = 0f

    private var tcpClient: TCPClient? = null

    private val scope = CoroutineScope(Job() + Dispatchers.IO)

//    private val lock = ReentrantLock()
//    private val waitLock = lock.newCondition()


    @SuppressLint("ClickableViewAccessibility")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_control)

        controlWindowInsets(true)

        val controlCircle = findViewById<ImageView>(R.id.control_image)

        val dip = 32f
        val r: Resources = resources
        this.pxMargin = TypedValue.applyDimension(
            TypedValue.COMPLEX_UNIT_DIP,
            dip,
            r.displayMetrics
        )

        val vto: ViewTreeObserver = controlCircle.viewTreeObserver
        vto.addOnPreDrawListener(object : ViewTreeObserver.OnPreDrawListener {
            override fun onPreDraw(): Boolean {
                controlCircle.viewTreeObserver.removeOnPreDrawListener(this)
                height = controlCircle.measuredHeight
                width = controlCircle.measuredWidth
                radius = width.coerceAtMost(height) / 2f
                println(radius)
                return true
            }
        })

        controlCircle.setOnTouchListener(
            object : View.OnTouchListener {
                override fun onTouch(view: View, motionEvent: MotionEvent): Boolean {
                    val touchX = motionEvent.x
                    val touchY = motionEvent.y
                    if (touchX < 0) {
                        return false
                    }
                    if (touchY < 0) {
                        return false
                    }

                    val coorX = touchX - width / 2
                    val coorY = touchY - height / 2

                    val length = sqrt(coorX.pow(2) + coorY.pow(2))
                    if (length < radius / 3) {
                        println("Standby")

                        sendMessageAsync("Standby")
                    } else if (length >= radius / 3 && length < 2 * radius / 3) {
                        var angle = atan2(coorY, coorX)
                        if (angle > -PI / 4 && angle <= PI / 4) {
                            println("Move right")

                            runBlocking { // this: CoroutineScope
                                launch { // launch a new coroutine and continue
                                    tcpClient?.sendMessage("Move right")
                                }
                            }
                        } else if (angle > PI / 4 && angle <= 3 * PI / 4) {
                            println("Move back")

                            runBlocking { // this: CoroutineScope
                                launch { // launch a new coroutine and continue
                                    tcpClient?.sendMessage("Move back")
                                }
                            }
                        } else if (angle > -3 * PI / 4 && angle < -PI / 4) {
                            println("Move forward")

                            runBlocking { // this: CoroutineScope
                                launch { // launch a new coroutine and continue
                                    tcpClient?.sendMessage("Move forward")
                                }
                            }
                        } else {
                            println("Move left")

                            runBlocking { // this: CoroutineScope
                                launch { // launch a new coroutine and continue
                                    tcpClient?.sendMessage("Move left")
                                }
                            }
                        }
                    } else if (length >= 2 * radius / 3 && length < radius) {
                        var angle = atan2(coorY, coorX)
                        if (angle > -PI / 4 && angle <= PI / 4) {
                            println("Turn right")

                            runBlocking { // this: CoroutineScope
                                launch { // launch a new coroutine and continue
                                    tcpClient?.sendMessage("Turn right")
                                }
                            }
                        } else if (angle > PI / 4 && angle <= 3 * PI / 4) {
                            println("Fast back")

                            runBlocking { // this: CoroutineScope
                                launch { // launch a new coroutine and continue
                                    tcpClient?.sendMessage("Fast back")
                                }
                            }
                        } else if (angle > -3 * PI / 4 && angle < -PI / 4) {
                            println("Fast forward")

                            runBlocking { // this: CoroutineScope
                                launch { // launch a new coroutine and continue
                                    tcpClient?.sendMessage("Fast forward")
                                }
                            }
                        } else {
                            println("Turn left")

                            runBlocking { // this: CoroutineScope
                                launch { // launch a new coroutine and continue
                                    tcpClient?.sendMessage("Turn left")
                                }
                            }
                        }
                    }
//                    val width = view.width
//                    val height = view.height
//                    println(width.toString().plus(":").plus(height.toString()))
//                    println(touchX.toString().plus(":").plus(touchY.toString()))
//                    println(coorX.toString().plus(":").plus(coorY.toString()))
//                    println(radius)
                    return true
                }
            }
        )
        this.tcpClient = TCPClient(this, "192.168.1.202", 1234, object : OnMessageReceived {
            override fun messageReceived(message: String?) {
                if (message == null) {
//                    alertDialog(DISCONNECTED)
                    println("no message")
                }
            }
        }, object : OnConnectEstablished {
            override fun onConnected() {
//                udpClient.start()
                println("connected")
            }
        }
        )
        this.tcpClient!!.start()
    }


    private fun controlWindowInsets(hide: Boolean) {
        // WindowInsetsController can hide or show specified system bars.
        val insetsController = window.decorView.windowInsetsController ?: return
        // The behavior of the immersive mode.
        val behavior = BehaviorOption.values()[1].value
        // The type of system bars to hide or show.
        val type = TypeOption.values()[0].value
        insetsController.systemBarsBehavior = behavior
        if (hide) {
            insetsController.hide(type)
        } else {
            insetsController.show(type)
        }
    }



    fun sendMessageAsync(message: String) {
        // Starts a new coroutine within the scope
        scope.launch {
            // New coroutine that can call suspend functions
//            suspend fun sendMessage(message: String) =                 // Dispatchers.Main
                withContext(Dispatchers.IO) {              // Dispatchers.IO (main-safety block)
                    tcpClient?.sendMessage(message)
                    /* perform network IO here */          // Dispatchers.IO (main-safety block)
                }
        }
    }

//    suspend fun sendMessage(message: String) =                 // Dispatchers.Main
//        withContext(Dispatchers.IO) {              // Dispatchers.IO (main-safety block)
//            tcpClient?.sendMessage(message)
//            /* perform network IO here */          // Dispatchers.IO (main-safety block)
//        }                                          // Dispatchers.Main
}

