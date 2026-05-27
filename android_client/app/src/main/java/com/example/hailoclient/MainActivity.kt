package com.example.hailoclient

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.os.Bundle
import android.provider.MediaStore
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.IOException

class MainActivity : AppCompatActivity() {

    private lateinit var imageView: ImageView
    private lateinit var btnSnap: Button
    private lateinit var serverUrlInput: EditText
    private lateinit var resultText: TextView

    private val client = OkHttpClient()

    private val takePicture = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == RESULT_OK) {
            val imageBitmap = result.data?.extras?.get("data") as? Bitmap
            if (imageBitmap != null) {
                imageView.setImageBitmap(imageBitmap)
                uploadImage(imageBitmap)
            } else {
                Toast.makeText(this, "Failed to capture image", Toast.LENGTH_SHORT).show()
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        imageView = findViewById(R.id.imageView)
        btnSnap = findViewById(R.id.btnSnap)
        serverUrlInput = findViewById(R.id.serverUrlInput)
        resultText = findViewById(R.id.resultText)

        btnSnap.setOnClickListener {
            val takePictureIntent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
            takePicture.launch(takePictureIntent)
        }
    }

    private fun uploadImage(bitmap: Bitmap) {
        val serverUrl = serverUrlInput.text.toString().trim()
        if (serverUrl.isEmpty()) {
            Toast.makeText(this, "Please enter server URL", Toast.LENGTH_SHORT).show()
            return
        }

        resultText.text = "Uploading..."
        
        val stream = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.JPEG, 90, stream)
        val byteArray = stream.toByteArray()

        val requestBody = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("file", "snap.jpg", byteArray.toRequestBody("image/jpeg".toMediaTypeOrNull()))
            .build()

        val request = Request.Builder()
            .url("$serverUrl/process-frame")
            .post(requestBody)
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                runOnUiThread {
                    resultText.text = "Error: ${e.message}"
                }
            }

            override fun onResponse(call: Call, response: Response) {
                val responseBody = response.body?.string() ?: ""
                runOnUiThread {
                    if (response.isSuccessful) {
                        try {
                            val json = JSONObject(responseBody)
                            if (json.optString("status") == "success") {
                                val detections = json.getJSONArray("detections")
                                resultText.text = "Found ${detections.length()} objects.\n$responseBody"
                                drawBoxes(bitmap, json)
                            } else {
                                resultText.text = "Error: ${json.optString("message")}"
                            }
                        } catch (e: Exception) {
                            resultText.text = "Failed to parse JSON: ${e.message}\nResponse: $responseBody"
                        }
                    } else {
                        resultText.text = "Server Error: ${response.code}\n$responseBody"
                    }
                }
            }
        })
    }

    private fun drawBoxes(originalBitmap: Bitmap, jsonResponse: JSONObject) {
        val mutableBitmap = originalBitmap.copy(Bitmap.Config.ARGB_8888, true)
        val canvas = Canvas(mutableBitmap)
        
        val paintBox = Paint().apply {
            color = Color.GREEN
            style = Paint.Style.STROKE
            strokeWidth = 3f
        }
        val paintText = Paint().apply {
            color = Color.GREEN
            textSize = 14f
            style = Paint.Style.FILL
        }

        val detections = jsonResponse.getJSONArray("detections")
        
        // Scale logic to match coordinates mapping
        val scaleX = mutableBitmap.width / 640f
        val scaleY = mutableBitmap.height / 640f

        for (i in 0 until detections.length()) {
            val det = detections.getJSONObject(i)
            val box = det.getJSONArray("box")
            val xmin = box.getDouble(0).toFloat() * scaleX
            val ymin = box.getDouble(1).toFloat() * scaleY
            val xmax = box.getDouble(2).toFloat() * scaleX
            val ymax = box.getDouble(3).toFloat() * scaleY
            val className = det.getString("class")
            val conf = det.getDouble("confidence")

            val rect = RectF(xmin, ymin, xmax, ymax)
            canvas.drawRect(rect, paintBox)
            canvas.drawText("$className (%.2f)".format(conf), xmin, ymin - 5, paintText)
        }

        imageView.setImageBitmap(mutableBitmap)
    }
}
