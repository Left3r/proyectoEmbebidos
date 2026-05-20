
// llamada a API con parametros JSON desde terminal
//curl -X POST http://192.168.1.97:5000/api/switch/pin -H "Content-Type: application/json" -d '{"pin_id": 46, "state": "false"}' \

// variables
let actionsTableData = [];
let dataGraph_table = {};
let chosenCardIndex;
const port = '5000';


const queueCommand = async (commandData) => {
    try{
        const response = await fetch('/api/queue/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(commandData)
        });

        if (!response.ok){
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
    }catch (err){
        console.error('Queue error', err);
    }
};


// =========================================================================================
// -- toggle switch --
const TOGGLE_SWITCH_PIN = 46;

const input = document.querySelector('.toggle-input');
input.addEventListener('change', async function(e){
    await queueCommand({
        'pin': TOGGLE_SWITCH_PIN,
        'cmd': 'toggle_led',
        'value': e.target.checked
    });  
})

// -- slider pwm --
const PWM_LED_PIN = 11;
const PWM_SLIDER = document.querySelector('#pwm-slider');
const PWM_LABEL = document.getElementById('pwm-slider-label');
//updates label
PWM_SLIDER.oninput = function () {
    PWM_LABEL.textContent = parseFloat(this.value) || 0;
}
//handler
PWM_SLIDER.addEventListener('change', async function(e){
    const pwmValue = parseFloat(e.target.value) || 0;
    await queueCommand({
        'pin': PWM_LED_PIN,
        'cmd': 'set_pwm',
        'value': pwmValue
    });
});


// -- boton pin 7 activo
const btnSquare = document.getElementById('btn-pin')
                          .querySelector('.square');

const listenBtnChange = setInterval (async function(){
    try{
        const response = await fetch('/api/btn/get', {
            method: 'GET',
        });

        if (!response.ok){
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        //actualiza el cuadro que representa el boton
        if (data['btn_bool']){
            btnSquare.style.backgroundColor = "#4CAF50"
        }else{
            btnSquare.style.backgroundColor = "#a0a0a0"
        }
    }catch (err){
        console.error('Queue error', err);
    }
}, 1500);


// -- grafica --
const ADC_PIN = 16;

const element = document.querySelector('.chart-container');
const startBtn = element.querySelector('.chart-start-btn');
const stopBtn = element.querySelector('.chart-stop-btn');
const stateDot = element.querySelector(`#chart-state-dot-1`);
const thresDot = element.querySelector(`#threshold-state-dot-1`);
const slider = element.querySelector(`#slider-1`)
const canvasId = element.querySelector('canvas').id;

let umbralValue = 1;
let umbralActive = false;
let thresholdDataPoints = [];
// let umbralPassed = false;
let intervalRate = slider.value;
let intervalId = null;
let isRunning = false;
let chartInstance = null;
let dataPoints = [];



// inicializa grafica
chartInstance = new Chart(document.getElementById(canvasId),{
    type:'line',
    data: {
        datasets: [
            {
                label: `Pin ${ADC_PIN}`,
                data: [],
                pointRadius: 2,
                pointBackgroundColor: '#120a68',
                borderColor: '#120a68',
                borderWidth: 2,
                tension: 0.1,
                fill: false
            },
            {
                label: 'Umbral',
                data: [],
                hidden: true,           // Start hidden
                pointRadius: 0,         // No dots
                borderColor: '#d11f3c',
                borderWidth: 2,
                borderDash: [6, 4],     // Dashed
                tension: 0,
                fill: false,
                yAxisID: 'y'            // Same axis, no dual-Y needed
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        animation:false,
        interaction: {
            mode: 'nearest',
            intersect: false
        },
        plugins: {
            legend: {display: true},
            tooltip: {
                callbacks: {
                    afterBody: (context) => {
                        if (context[0].datasetIndex !== 0) return '';
                        const val = context[0].parsed.y;
                        const status = umbralActive 
                            ? (val > umbralValue ? 'ARRIBA DE UMBRAL': 'Bajo umbral')
                            : '';
                        return status;
                    }
                }
            },
        },
        scales: {
            x: {
                type:'time',
                time:{
                    parser: 'HH:mm:ss',
                    unit: 'second',
                    displayFormats:{
                        second:'HH:mm:ss',
                        minute:'HH:mm:ss',
                        hour:'HH:mm'
                    }
                },
                title: {display:true, text: 'Time(s)'},
                grid: { color: 'rgba(0,0,0,0.05)' }
            },
            y: {
                min:0,
                max:10, // voltaje
                title: {display: true, text:'Voltage (v)'},
                grid: { color: 'rgba(0,0,0,0.05)' }
            },
        }
    },
});


// polling function: agrega datos a la grafica con el endpoint
async function pollData(){
    try{
            const response = await fetch(`/api/adc/get`);
            
            if (response.status === 204){
                return;
            }
            
            if (!response.ok){
                throw new Error('HTTP ' + response.status);
            } 
            const data = await response.json();
            const now = new Date().toISOString().split('T')[1].split('.')[0];
            dataPoints.push({
                x: now,
                y: data.voltage
            });

            if (umbralActive){
                thresholdDataPoints.push({
                    x:now,
                    y:umbralValue
                });
            }else{
                thresholdDataPoints.push(null);
            }

            // keep last 50 points
            if (dataPoints.length > 50){
                dataPoints.shift();
                thresholdDataPoints.shift();
            } 
            // update chart
            chartInstance.data.datasets[0].data = dataPoints;
            chartInstance.data.datasets[1].data = thresholdDataPoints;
            
            // Threshold
            if (umbralActive) {
                const isOver = data.voltage > umbralValue;
                thresDot.style.backgroundColor = isOver ? '#d71717' :'#4CAF50';
               
            }
            chartInstance.update('none');
        }catch (err){
            console.error('Poll failed:', err);
        }
}

// --- controles ---

//updates graph slider label
slider.oninput = function () {
    document.getElementById('timeValue-1').textContent = parseFloat(this.value) || 0;
}

//change interval on slider change
slider.addEventListener('change', (e)=>{
    const newRate = parseInt(e.target.value);
    if (isRunning && newRate !== intervalRate){
        //restart interval
        clearInterval(intervalId);
        intervalId = setInterval(pollData, newRate * 1000)
    }
    intervalRate = newRate
})


// start button: data polling
startBtn.addEventListener('click', async function(){
    // startBtn.style.backgroundColor = 'red';
    stateDot.style.backgroundColor = '#1fa41a';
    if (isRunning) return;
    isRunning = true;
    startBtn.disabled = true;
    stopBtn.disabled = false;

    // start graph
    await queueCommand({
        'pin': ADC_PIN,
        'cmd': 'graph_is_active',
        'value': null
    });

    // polling
    intervalId = setInterval(pollData, parseInt(intervalRate) * 1000); //200 5hz update rate
});

// stop button: pause polling
stopBtn.addEventListener('click', async function(){
    // startBtn.style.backgroundColor = 'green';
    stateDot.style.backgroundColor = '#b2b8bc';

    isRunning = false;
    clearInterval(intervalId);
    startBtn.disabled = false;
    stopBtn.disabled = true;

    // stop graph
    await queueCommand({
        'pin': ADC_PIN,
        'cmd': 'graph_is_inactive',
        'value': null
    });

});

//-- umbral ---
const umbralInput = document.getElementById('umbral-value');
const umbralToggle = document.getElementById('umbral');

umbralInput.addEventListener('input', (e)=> {
    umbralValue = parseFloat(e.target.value) || 0;
    if(umbralActive){
        // reconstruye datos de umbral 
        thresholdDataPoints = dataPoints.map(point => ({
            x: point.x,
            y: umbralValue
        }));
        chartInstance.data.datasets[1].data = thresholdDataPoints;
        chartInstance.data.datasets[1].hidden = false;  // Ensure it stays visible
        chartInstance.update('none');
    }
});

umbralToggle.addEventListener('change', (e)=>{
    umbralActive = e.target.checked;

    const thresholdDataset = chartInstance.data.datasets[1];
    thresholdDataset.hidden = !umbralActive;
    
    if (umbralActive){
        thresholdDataPoints = dataPoints.map(point => ({
            x: point.x,
            y: umbralValue
        }));
        thresholdDataset.data = thresholdDataPoints;
    }else{
        thresholdDataPoints = [];
        thresholdDataset.data = [];
        chartInstance.data.datasets[0].pointBackgroundColor = '#120a68';
    }
    chartInstance.update('none');
});



// ---
element.cleanup = () => {
    clearInterval(intervalId);
    chartInstance.destroy();
}


// -- reinicia sliders
window.onload = function(){
    input.checked = false;
    PWM_SLIDER.value = 0;
    slider.value = 5;
};

