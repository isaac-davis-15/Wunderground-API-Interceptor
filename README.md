# Weather Underground API Interceptor
Hi!
This repository contains some code that I wrote to intercept and process API calls to the Weather Underground API. Here is a story
## Preamble
For Christmas of 2024, I received a SainLogic Weather Station. 
![SainLogic Weather Station with Basestation](https://crdms.images.consumerreports.org/f_auto,w_1200/prod/products/cr/models/416065-weather-stations-sainlogic-wifi-weather-station-10041681.png)
This thing was sick!!! It provided the following metrics:
* Temperature
* Humidity
* Pressure
* Wind Speed
* Wind Direction
* Daily Rain Total
* Rainfall Rate
* Solar Radiation and UV 
* And other metrics calculated from the above

Now with all these metrics, the station would provide raw sensor data to a base station that would display all of this data. Now if your particularly tech savvy, you could connect the base station to your Wi-Fi, sign up for Weather Underground or Weather Cloud, get an API key, and program the API key into the base station via its onboard WebUI. This way you are able to view your weather data on Weather Underground or Weather Cloud; all while providing your weather data to them to make forecasts and to provide to others. 

## My "Old Man Yells at Cloud" Moment
Now as many IT professionals and Homelabers know, providers of cloud services reserve the right to use the data you provide them as they see fit. That is a big part of what Homelabing is, your want your data to say on your own servers and network as much as possible. 

So seeing that my only options for viewing "my" weather data was to use a backlit liquid crystal display (Which does not even show historical data) or send my data to a cloud service; I thought there had to be a different way.

## How this works
Looking at the way the weather station sent weather data, it was easy to see that this mechanism could be gamed. 
### DNS
First the Weather station would make a DNS lookup request on 

> rtupdate.wunderground.com

More importantly, it would use the DNS server specified during its DHCP handshake to make this request, not anything hardcoded; this will be important later.
### REST API
Once the Weather Station had the DNS response, it would start a TCP connection with the IP address retrieved from the DNS query. Once the TCP socket was successfully initialized, the Weather Station would make the following HTTP GET request:
```
/weatherstation/updateweatherstation.php?
ID=[REDACTED]&
PASSWORD=[NO API KEYS FOR YOU]&
indoortempf=64.8&
indoorhumidity=52&
tempf=76.2&
humidity=29&
dewptf=41.6&
windchillf=76.2&
absbaromin=29.01&
baromin=29.89&
windspeedmph=1.1&
windgustmph=2.2&
winddir=0&
windspdmph_avg2m=1.6&
winddir_avg2m=293&
windgustmph_10m=2.2&
windgustdir_10m=113&
rainin=0.0&
dailyrainin=0.0&
weeklyrainin=0.05&
monthlyrainin=0.22&
solarradiation=112.41&
UV=2&
dateutc=2025-5-6%2020:47:56&
action=updateraw&
realtime=1&
rtfreq=5&
```
Before you ask, yes, this is live data from my weather station, as you can see by the date code on this HTTP request.

#### A quick rant
It should also be noted that when I say HTTP, I mean HTTP. Turns out this thing does not even try to encrypt or use SSL/TLS. I can somewhat understand not wanting to implement encryption or SSL on an imbedded device like a weather station. But only when you are not transmitting API keys and Identifiable information in the clear. Why? Also Weather Underground really should require SSL and send a 300 HTTP redirect anytime someone tries to use an unsecured HTTP socket. It is their API keys after all that they allow Weather Station manufactures to send in the clear

Rant over....

### Putting it all together
So, if we are able to manipulate the DNS response to the Weather Station when it tries to resolve rtupdate.wunderground.com, we can have the weather station just send the data to whatever IP address we want via HTTP (I guess that is the only good thing that comes with not using HTTPS; no certificate verification). 

First, I spin up a small HTTP server using Python that checks if the incoming HTTP requests ends with "/updateweatherstation.php". If not, then it just returns a HTTP 404 and closes the connection.
```python
if not parsed.path.endswith("/updateweatherstation.php"):
    self.send_response(404)
    self.end_headers()
    return
```
Second, if the request meets the above restriction, it will then strip all the GET parameters off of the request in a key/value format, convert the value to a float and set a pre-established Prometheus gauge object to the value.
```python
query = parse_qs(parsed.query)
# Update each gauge if present
for key, gauge in gauges.items():
    if key in query:
        try:
            # take the first value and convert to float
            val = float(query[key][0])
            gauge.set(val)
        except ValueError:
            pass  # ignore non-numeric
# respond so station thinks it succeeded
self.send_response(200)
self.end_headers()
``` 
So every time the Weather Station sends data to this HTTP server, it will update Prometheus Gauge values to the values given by the weather station. To tie all this up in a bow, we pull double duty on the HTTP server and provide the gauges to a Prometheus DB server.
```python
if parsed.path == "/metrics":
    # Serve Prometheus metrics
    output = generate_latest(registry)
    self.send_response(200)
    self.send_header("Content-Type", CONTENT_TYPE_LATEST)
    self.end_headers()
    self.wfile.write(output)
else:
    # Treat any other GET as a data push from the WeatherStation
    self.handle_update(parsed)
```

Then we can have our Prometheus DB server query this HTTP server and get time series data from the HTTP server.

### Overriding DNS
Now the real question. Can we trick the Weather Station to send the reports to our HTTP server? 
> yes....

As mentioned earlier, it turns out the the weather station will use DNS servers specified in the DHCP handshake when the weather station first connects to a local network. I'm not sure what DNS servers it will default to when no DNS servers are specified in DHCP, but that does not matter at this point. I can specify a DNS server that responds to the Weather Stations DNS request for 'rtupdate.wunderground.com' with my HTTP server's IP address. Then the Weather Station will send the HTTP request to our own server, rather than what public IP address 'rtupdate.wunderground.com' actually resolves to

## Running the HTTP Server
You will have to spin up a DNS server of your choice (And add a DNS entry for the API URL) and change your local DHCP server to point to it. However, once you have that complete you can build and run this docker container to create a Prometheus metric source for the weather data!
### Build the Image
```bash
git clone https://github.com/isaac-davis-15/Wunderground-API-Interceptor
cd ./Wunderground-API-Interceptor
docker build -t author/name ./ # The author/name can be anything. Just remember it for later
```
### Run the Image
```bash
docker run -e PORT=80 author/name
```
You may, depending if you plan to run any other services on the hypervisor server, you may need to create a special network configuration to give the container a unique IP address on your network. Port mapping to port 80 on your docker instance may not work. Alternatively, you may be able to use a reverse proxy to map to any port; this is untested however. Running the container, we see it work!
```bash
🚀  Starting weatherstation exporter on :80

 - data pushes: /weatherstation/updateweatherstation.php?...

 - metrics scrape: /metrics
```

Nice!

## Visualization
Once we get a Prometheus server pulling data from our HTTP server, we can then connect Grafana or another data visualizer to graph historical changes. Keeping all data within your own network
## Future Plans
I plan to give an option to forward the HTTP request back to the real servers. That way a user can choose to send the data to wunderground. I also eventually plan to be able to pull data from USGS river data. I live near a river and would like to keep data on river height
