package com.islamdetector.aipro;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Color;
import android.view.View;

/**
 * Relative 3D scan workspace.
 * It intentionally draws an empty reference grid until real spatial telemetry
 * is available; it never invents soil layers, voids, or metal targets.
 */
public final class GroundMapView extends View {
    private final Paint grid = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint edge = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint text = new Paint(Paint.ANTI_ALIAS_FLAG);
    private float zoom = 1.0f;
    private boolean automaticScale = true;

    public GroundMapView(Context context) {
        super(context);
        grid.setColor(Color.rgb(70, 126, 145));
        grid.setStrokeWidth(1.5f);
        grid.setStyle(Paint.Style.STROKE);
        edge.setColor(Color.rgb(117, 176, 174));
        edge.setStrokeWidth(2.4f);
        edge.setStyle(Paint.Style.STROKE);
        text.setColor(Color.rgb(192, 211, 222));
        text.setTextSize(32f);
    }

    public void zoomIn() {
        automaticScale = false;
        zoom = Math.min(zoom * 1.2f, 2.5f);
        invalidate();
    }

    public void zoomOut() {
        automaticScale = false;
        zoom = Math.max(zoom / 1.2f, 0.55f);
        invalidate();
    }

    public void useAutomaticScale() {
        automaticScale = true;
        zoom = 1.0f;
        invalidate();
    }

    public boolean isAutomaticScale() {
        return automaticScale;
    }

    public void setScaleState(float value, boolean automatic) {
        zoom = Math.max(0.55f, Math.min(value, 2.5f));
        automaticScale = automatic;
        invalidate();
    }

    private float px(float x, float y, float cx, float unit) {
        return cx + (x - y) * unit * 0.72f;
    }

    private float py(float x, float y, float top, float unit) {
        return top + (x + y) * unit * 0.34f;
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float w = getWidth();
        float h = getHeight();
        float cx = w * 0.5f;
        float unit = Math.min(w / 10.5f, h / 8.0f) * zoom;
        float top = h * 0.20f;

        // Top reference plane: relative grid only, not a measured soil map.
        Path outline = new Path();
        outline.moveTo(px(0, 0, cx, unit), py(0, 0, top, unit));
        outline.lineTo(px(6, 0, cx, unit), py(6, 0, top, unit));
        outline.lineTo(px(6, 6, cx, unit), py(6, 6, top, unit));
        outline.lineTo(px(0, 6, cx, unit), py(0, 6, top, unit));
        outline.close();
        canvas.drawPath(outline, edge);

        for (int i = 1; i < 6; i++) {
            canvas.drawLine(px(i, 0, cx, unit), py(i, 0, top, unit),
                    px(i, 6, cx, unit), py(i, 6, top, unit), grid);
            canvas.drawLine(px(0, i, cx, unit), py(0, i, top, unit),
                    px(6, i, cx, unit), py(6, i, top, unit), grid);
        }

        // Vertical depth guides are reference axes, not detected strata.
        float depth = unit * 1.45f;
        for (int i = 0; i <= 6; i += 2) {
            float x = px(i, 6, cx, unit);
            float y = py(i, 6, top, unit);
            canvas.drawLine(x, y, x, y + depth, grid);
        }
        canvas.drawLine(px(0, 6, cx, unit), py(0, 6, top, unit) + depth,
                px(6, 6, cx, unit), py(6, 6, top, unit) + depth, grid);

        text.setTextAlign(Paint.Align.CENTER);
        canvas.drawText("شبكة المسح النسبية", cx, h * 0.08f, text);
        text.setTextSize(24f);
        canvas.drawText(automaticScale ? "المقياس: تلقائي" : "المقياس: يدوي",
                cx, h * 0.94f, text);
    }
}
