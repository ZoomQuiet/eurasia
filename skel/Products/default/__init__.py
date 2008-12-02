def controller(client):
	client.write(template200(version=client.version))
	client.close()

template200 = __import__('string').Template(

'''\
${version} 200 OK
Content-Type: text/html

<html>
<head>
<title>Eurasia3 Default Page</title>
</head>
<body>
<h1>It works!</h1>
</body>
</html>''' ).substitute
